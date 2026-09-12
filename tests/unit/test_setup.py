"""T04 — setup por perfil: descoberta por IDs, desambiguação e limitações. V10 e V13."""

import json
from contextlib import contextmanager
from pathlib import Path

import pytest
import yaml

from ado_team_compass.adapters.ado_mcp import AdoMcpClient
from ado_team_compass.cli import main
from ado_team_compass.config import resolve_config
from ado_team_compass.config.setup import (
    build_config_document,
    discover,
    slugify,
    write_config_document,
)
from ado_team_compass.contracts.config import ProfileName
from ado_team_compass.errors import ConfigError, ExitCode
from ado_team_compass.mcp.session import FixtureTransport, ToolDescriptor
from ado_team_compass.mcp.session.transport import schema_hash

TOOLS = (
    "core_list_projects",
    "core_list_project_teams",
    "work_get_team_settings",
    "work_list_team_iterations",
    "wit_list_work_items_for_iteration",
    "wit_get_work_items_batch",
)


def _transport(responses: dict[str, object], names: tuple[str, ...] = TOOLS) -> FixtureTransport:
    return FixtureTransport(
        tools=tuple(
            ToolDescriptor(name=name, input_schema_hash=schema_hash({"properties": {}}))
            for name in names
        ),
        responses=responses,
    )


def _default_responses() -> dict[str, object]:
    return {
        "core_list_projects": {"value": [{"id": "proj-1", "name": "Plataforma"}]},
        "core_list_project_teams": {
            "value": [{"id": "team-1", "name": "Core"}, {"id": "team-2", "name": "Suporte"}]
        },
        "work_get_team_settings": [
            {"teamFieldValues": [{"value": "Plataforma\\Core", "includeChildren": True}]},
            {"teamFieldValues": [{"value": "Plataforma\\Suporte", "includeChildren": False}]},
        ],
        "work_list_team_iterations": [
            {"value": [{"path": "Plataforma\\Sprint 42"}]},
            {"value": []},
        ],
    }


def _client(responses: dict[str, object], names: tuple[str, ...] = TOOLS) -> AdoMcpClient:
    return AdoMcpClient(transport=_transport(responses, names))


def test_discovery_uses_stable_ids_and_declared_scope():
    discovery = discover(_client(_default_responses()), organization="contoso")
    assert [team.team_id for team in discovery.teams] == ["team-1", "team-2"]
    core = discovery.teams[0]
    assert core.project_id == "proj-1"
    assert core.area_paths == ("Plataforma\\Core",)
    assert core.include_descendants is True
    assert core.iterations == ("Plataforma\\Sprint 42",)
    assert "mcp:get_team_settings" in core.provenance


# V13 — nomes iguais em projetos diferentes.
def test_v13_homonymous_teams_are_disambiguated_by_project_and_id():
    responses = {
        "core_list_projects": {
            "value": [{"id": "proj-1", "name": "Plataforma"}, {"id": "proj-2", "name": "Dados"}]
        },
        "core_list_project_teams": [
            {"value": [{"id": "team-1", "name": "Core"}]},
            {"value": [{"id": "team-9", "name": "Core"}]},
        ],
        "work_get_team_settings": [{}, {}],
        "work_list_team_iterations": [{"value": []}, {"value": []}],
    }
    discovery = discover(_client(responses), organization="contoso")
    aliases = discovery.aliases()
    assert set(aliases) == {"plataforma-core", "dados-core"}
    assert aliases["dados-core"].team_id == "team-9"


def test_renaming_does_not_change_identity():
    discovery = discover(_client(_default_responses()), organization="contoso")
    document = build_config_document(discovery)
    ids = {team["team_id"] for team in document["teams"]}
    assert ids == {"team-1", "team-2"}


# V10 — equipe sem iterações nem capacidade continua configurável.
def test_v10_team_without_iterations_is_configurable_with_an_explicit_limitation():
    responses = _default_responses()
    responses["work_list_team_iterations"] = [{"value": []}, {"value": []}]
    discovery = discover(_client(responses), organization="contoso")
    assert discovery.teams[1].iterations == ()
    document = build_config_document(discovery)
    resolved = resolve_config(document)
    assert resolved.config.teams[0].profile is ProfileName.SPRINT_WITHOUT_HOURS


def test_missing_catalog_tools_become_declared_limitations():
    discovery = discover(
        _client(_default_responses(), names=("core_list_projects", "core_list_project_teams")),
        organization="contoso",
    )
    notes = " ".join(discovery.teams[0].limitations)
    assert "configuração da equipe não exposta" in notes
    assert "iterações não expostas" in notes


def test_projects_operation_absent_stops_with_a_limitation_not_a_crash():
    discovery = discover(
        _client(_default_responses(), names=("core_list_project_teams",)),
        organization="contoso",
    )
    assert discovery.teams == []
    assert any("projetos não descobertos" in note for note in discovery.limitations)


def test_team_settings_without_areas_asks_for_explicit_configuration():
    responses = _default_responses()
    responses["work_get_team_settings"] = [{}, {}]
    discovery = discover(_client(responses), organization="contoso")
    assert discovery.teams[0].area_paths == ()
    assert any("áreas da equipe não vieram" in note for note in discovery.teams[0].limitations)


def test_descendant_inclusion_unknown_is_reported_instead_of_assumed():
    responses = _default_responses()
    responses["work_get_team_settings"] = [
        {"teamFieldValues": [{"value": "Plataforma\\Core"}]},
        {},
    ]
    discovery = discover(_client(responses), organization="contoso")
    team = discovery.teams[0]
    assert team.include_descendants is None
    assert any("descendentes" in note for note in team.limitations)
    document = build_config_document(discovery)
    assert "include_descendants" not in document["teams"][0].get("scope", {})


def test_generated_document_is_valid_and_has_no_credentials():
    discovery = discover(_client(_default_responses()), organization="contoso")
    document = build_config_document(discovery, timezone="America/Sao_Paulo")
    resolved = resolve_config(document)
    assert (
        resolved.config.connections[0]
        .server.resolved_url("contoso")
        .startswith("https://mcp.azuredevops.com/")
    )
    assert "token" not in json.dumps(document).lower()
    assert resolved.config.teams[0].calendar.timezone == "America/Sao_Paulo"


def test_profiles_can_be_chosen_per_team():
    discovery = discover(_client(_default_responses()), organization="contoso")
    document = build_config_document(discovery, profiles={"core": ProfileName.SPRINT_WITH_CAPACITY})
    profiles = {team["alias"]: team["profile"] for team in document["teams"]}
    assert profiles["core"] == "sprint_with_capacity"
    assert profiles["suporte"] == "sprint_without_hours"


def test_write_refuses_to_overwrite_and_accepts_explicit_force(tmp_path):
    document = build_config_document(
        discover(_client(_default_responses()), organization="contoso")
    )
    destination = tmp_path / "nested" / "config.yaml"
    write_config_document(document, destination)
    assert yaml.safe_load(destination.read_text(encoding="utf-8"))["schema_version"] == "1.0"
    with pytest.raises(ConfigError) as error:
        write_config_document(document, destination)
    assert error.value.code == "E_CFG_JA_EXISTE"
    write_config_document(document, destination, force=True)


def test_slugify_handles_accents_and_spaces():
    assert slugify("Produção & Integração") == "producao-integracao"


def test_cli_setup_writes_configuration_using_the_injected_transport(tmp_path, capsys):
    transport = _transport(_default_responses())

    @contextmanager
    def factory(_connection):
        yield transport

    destination = tmp_path / "config.yaml"
    from ado_team_compass.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["setup", "--organization", "contoso", "--output", str(destination)])
    args._transport_factory = factory
    assert int(args._handler(args)) == int(ExitCode.OK)
    summary = json.loads(capsys.readouterr().out)
    assert summary["organization"] == "contoso"
    assert Path(summary["config_path"]) == destination
    assert {team["alias"] for team in summary["teams"]} == {"core", "suporte"}


def test_cli_setup_requires_organization_and_refuses_offline():
    assert main(["setup"]) == int(ExitCode.INVALID_INPUT)
    assert main(["setup", "--organization", "contoso", "--offline"]) == int(ExitCode.INVALID_INPUT)
