"""T03/T04 — diagnóstico: ambiente, configuração, catálogo e ausência de segredos."""

import json
from contextlib import contextmanager
from pathlib import Path

from ado_team_compass.cli import main
from ado_team_compass.config import load_config
from ado_team_compass.diagnostics import diagnose
from ado_team_compass.errors import ExitCode
from ado_team_compass.mcp.session import FixtureTransport, ToolDescriptor
from ado_team_compass.mcp.session.transport import ToolCallResult, schema_hash

EXAMPLE = Path("examples/config/config.yaml")

FULL_CATALOG = (
    "core_list_project_teams",
    "work_list_team_iterations",
    "work_get_team_capacity",
    "work_get_iteration_capacities",
    "wit_list_work_items_for_iteration",
    "wit_get_work_items_batch",
    "wit_update_work_item",
)


def _factory(names=FULL_CATALOG, error: Exception | None = None):
    @contextmanager
    def factory(_connection):
        if error is not None:
            raise error
        yield FixtureTransport(
            tools=tuple(
                ToolDescriptor(name=name, input_schema_hash=schema_hash({"properties": {}}))
                for name in names
            )
        )

    return factory


def test_doctor_reports_environment_configuration_and_catalog():
    resolved = load_config(EXAMPLE)
    report, exit_code = diagnose(resolved, transport_factory=_factory())
    assert exit_code is ExitCode.OK
    assert report["access_channel"] == "mcp-oficial-microsoft"
    assert report["configuration"]["status"] == "valida"
    aliases = [team["alias"] for team in report["configuration"]["teams"]]
    assert aliases == ["plataforma", "suporte"]
    connection = report["connections"][0]
    assert connection["status"] == "conectado"
    assert connection["endpoint"] == "https://mcp.azuredevops.com/contoso/mcp"
    assert connection["catalog_hash"].startswith("sha256:")
    assert "wit_update_work_item" in connection["rejected_write_tools"]
    assert connection["missing_required_operations"] == []


def test_doctor_reports_missing_required_operations_as_partial():
    resolved = load_config(EXAMPLE)
    report, exit_code = diagnose(
        resolved, transport_factory=_factory(names=("core_list_project_teams",))
    )
    assert exit_code is ExitCode.PARTIAL_CAPABILITY
    missing = report["connections"][0]["missing_required_operations"]
    assert "get_team_capacity" in missing and "get_work_items_batch" in missing


def test_doctor_offline_validates_configuration_and_declares_collection_unavailable():
    resolved = load_config(EXAMPLE)
    report, exit_code = diagnose(resolved, offline=True)
    assert exit_code is ExitCode.PARTIAL_CAPABILITY
    assert report["connections"] == []
    assert any("modo offline" in note for note in report["limitations"])


def test_doctor_without_configuration_is_actionable():
    report, exit_code = diagnose(None)
    assert exit_code is ExitCode.INVALID_INPUT
    assert any("setup" in note for note in report["limitations"])


def test_doctor_surfaces_authentication_failure_without_exposing_secrets():
    from ado_team_compass.errors import AccessError

    resolved = load_config(EXAMPLE)
    failure = AccessError(
        "E_MCP_AUTENTICACAO",
        "sessão inválida",
        detail={"access_token": "segredo"},
        remediation="autentique a sessão do MCP oficial",
    )
    report, exit_code = diagnose(resolved, transport_factory=_factory(error=failure))
    assert exit_code is ExitCode.ACCESS_DENIED
    assert report["connections"][0]["error"]["code"] == "E_MCP_AUTENTICACAO"
    assert "segredo" not in json.dumps(report, ensure_ascii=False)


def test_cli_doctor_uses_the_configuration_and_emits_json(capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("ADO_TEAM_COMPASS_CONFIG", str(EXAMPLE))
    assert main(["doctor", "--offline"]) == int(ExitCode.PARTIAL_CAPABILITY)
    payload = json.loads(capsys.readouterr().out)
    assert payload["offline"] is True
    assert payload["configuration"]["schema_version"] == "1.0"


def test_cli_doctor_without_configuration_returns_invalid_input(capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("ADO_TEAM_COMPASS_CONFIG", str(tmp_path / "ausente.yaml"))
    assert main(["doctor", "--offline"]) == int(ExitCode.INVALID_INPUT)
    assert "setup" in capsys.readouterr().out


def test_cli_doctor_with_explicit_missing_path_is_an_input_error(capsys, tmp_path):
    assert main(["doctor", "--config", str(tmp_path / "nao-existe.yaml")]) == int(
        ExitCode.INVALID_INPUT
    )
    assert "E_CFG_ARQUIVO_AUSENTE" in capsys.readouterr().err


def test_fixture_transport_never_reaches_the_network():
    transport = FixtureTransport(responses={"x": ToolCallResult(tool="x", payload=1)})
    assert transport.description.startswith("fixture://")
