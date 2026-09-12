"""T02 — precedência determinística, validação e sanitização da configuração."""

from decimal import Decimal
from pathlib import Path

import pytest

from ado_team_compass.config import load_config, load_yaml_document, resolve_config
from ado_team_compass.contracts.common import Capability
from ado_team_compass.contracts.config import CurrentDayPolicy, ProfileName
from ado_team_compass.errors import ConfigError, ExitCode, SchemaVersionError

EXAMPLE = Path("examples/config/config.yaml")


def _document(**overrides):
    document = {
        "schema_version": "1.0",
        "connections": [
            {
                "alias": "contoso",
                "organization": "contoso",
                "server": {"transport": "stdio", "command": ["npx", "@azure-devops/mcp"]},
            }
        ],
        "teams": [
            {
                "alias": "web",
                "connection": "contoso",
                "project_id": "p1",
                "team_id": "t1",
                "profile": "sprint_with_capacity",
            }
        ],
    }
    document.update(overrides)
    return document


def test_example_configuration_is_valid_and_versionable():
    resolved = load_config(EXAMPLE)
    assert [team.alias for team in resolved.config.teams] == ["plataforma", "suporte"]
    assert resolved.config.team("suporte").profile is ProfileName.CONTINUOUS_FLOW
    assert resolved.config.team("plataforma").calendar.current_day_policy is (
        CurrentDayPolicy.EXCLUDE
    )


def test_profile_defaults_apply_before_team_values():
    resolved = resolve_config(_document())
    team = resolved.config.team("web")
    # Vem do perfil empacotado.
    assert team.process.accounting_level == "leaf_task"
    assert team.allocation.unit == "hours"
    assert Capability.ALLOCATION in team.capabilities
    assert resolved.layer_of("teams.web.process.accounting_level") == "profile"


def test_team_overrides_profile_and_local_overrides_team():
    document = _document()
    document["teams"][0]["allocation"] = {"unit": "days"}
    local = {"teams": {"web": {"allocation": {"unit": "points"}}}}
    resolved = resolve_config(document, local_document=local)
    assert resolved.config.team("web").allocation.unit == "points"
    assert resolved.layer_of("teams.web.allocation.unit") == "local"


def test_run_overrides_win_over_every_other_layer():
    document = _document()
    document["teams"][0]["allocation"] = {"unit": "days"}
    resolved = resolve_config(
        document,
        local_document={"teams": {"web": {"allocation": {"unit": "points"}}}},
        run_overrides={"teams": {"web": {"allocation": {"unit": "hours"}}}},
    )
    assert resolved.config.team("web").allocation.unit == "hours"
    assert resolved.layer_of("teams.web.allocation.unit") == "run"


def test_wildcard_run_override_applies_before_alias_specific_override():
    document = _document()
    resolved = resolve_config(
        document,
        run_overrides={
            "teams": {
                "*": {"calendar": {"timezone": "UTC", "current_day_policy": "include_full"}},
                "web": {"calendar": {"timezone": "America/Sao_Paulo"}},
            }
        },
    )
    team = resolved.config.team("web")
    assert team.calendar.timezone == "America/Sao_Paulo"
    assert team.calendar.current_day_policy is CurrentDayPolicy.INCLUDE_FULL


def test_untouched_keys_are_attributed_to_product_defaults():
    resolved = resolve_config(_document())
    assert resolved.layer_of("teams.web.output.retention_days") == "product_default"
    assert resolved.config.output.retention_days == 30
    assert resolved.config.output.summary_limit_bytes == 24576


def test_unknown_major_schema_version_is_actionable_and_maps_to_exit_6():
    with pytest.raises(SchemaVersionError) as error:
        resolve_config(_document(schema_version="9.0"))
    assert error.value.code == "E_CFG_SCHEMA_MAJOR_DESCONHECIDA"
    assert error.value.exit_code == ExitCode.SCHEMA_INCOMPATIBLE
    assert error.value.remediation


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ({"schema_version": None}, "E_CFG_SCHEMA_AUSENTE"),
        ({"schema_version": "1"}, "E_CFG_SCHEMA_INVALIDO"),
        ({"teams": []}, "E_CFG_EQUIPES_AUSENTES"),
        ({"teams": ["web"]}, "E_CFG_EQUIPE_INVALIDA"),
    ],
)
def test_invalid_documents_produce_stable_codes(mutation, expected_code):
    document = _document()
    document.update(mutation)
    if mutation.get("schema_version", "keep") is None:
        document.pop("schema_version")
    with pytest.raises(ConfigError) as error:
        resolve_config(document)
    assert error.value.code == expected_code


def test_unknown_field_is_rejected_with_violation_path():
    document = _document()
    document["teams"][0]["velocidade_magica"] = 42
    with pytest.raises(ConfigError) as error:
        resolve_config(document)
    assert error.value.code == "E_CFG_INVALIDA"
    paths = [violation["path"] for violation in error.value.detail["violations"]]
    assert any("velocidade_magica" in path for path in paths)


def test_team_referencing_unknown_connection_is_rejected():
    document = _document()
    document["teams"][0]["connection"] = "outra"
    with pytest.raises(ConfigError) as error:
        resolve_config(document)
    assert error.value.code == "E_CFG_INVALIDA"


def test_duplicate_team_alias_is_rejected():
    document = _document()
    document["teams"].append(dict(document["teams"][0], team_id="t2"))
    with pytest.raises(ConfigError):
        resolve_config(document)


def test_credentials_are_not_representable_in_configuration():
    document = _document()
    document["connections"][0]["server"]["access_token"] = "abc"
    with pytest.raises(ConfigError) as error:
        resolve_config(document)
    assert error.value.code == "E_CFG_SEGREDO_NA_CONFIGURACAO"
    assert "abc" not in str(error.value.detail)


def test_credentials_are_rejected_in_local_layer_too():
    with pytest.raises(ConfigError) as error:
        resolve_config(_document(), local_document={"teams": {"web": {"ado_pat": "abc"}}})
    assert error.value.code == "E_CFG_SEGREDO_NA_CONFIGURACAO"


def test_threshold_order_is_validated():
    document = _document()
    document["teams"][0]["allocation"] = {"thresholds": {"below_range": "1.5"}}
    with pytest.raises(ConfigError):
        resolve_config(document)


def test_unknown_timezone_is_rejected():
    document = _document()
    document["teams"][0]["calendar"] = {"timezone": "Marte/Olympus"}
    with pytest.raises(ConfigError):
        resolve_config(document)


def test_stdio_transport_requires_command():
    document = _document()
    document["connections"][0]["server"] = {"transport": "stdio"}
    with pytest.raises(ConfigError):
        resolve_config(document)


def test_unknown_profile_is_actionable():
    document = _document()
    document["teams"][0]["profile"] = "scrumban_mistico"
    with pytest.raises(ConfigError) as error:
        resolve_config(document)
    assert error.value.code == "E_CFG_PERFIL_DESCONHECIDO"


def test_effective_config_is_sanitized_and_serializable():
    resolved = resolve_config(_document())
    assert resolved.effective["teams"][0]["alias"] == "web"
    assert "access_token" not in str(resolved.effective)


def test_local_teams_must_be_a_mapping():
    with pytest.raises(ConfigError) as error:
        resolve_config(_document(), local_document={"teams": [{"alias": "web"}]})
    assert error.value.code == "E_CFG_LOCAL_INVALIDO"


def test_missing_file_is_actionable(tmp_path):
    with pytest.raises(ConfigError) as error:
        load_yaml_document(tmp_path / "ausente.yaml")
    assert error.value.code == "E_CFG_ARQUIVO_AUSENTE"


def test_yaml_tags_are_not_evaluated(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("!!python/object/apply:os.system ['echo oops']\n", encoding="utf-8")
    with pytest.raises(ConfigError) as error:
        load_yaml_document(path)
    assert error.value.code == "E_CFG_YAML_INVALIDO"


def test_personal_availability_is_explicit_and_typed():
    local = {
        "teams": {
            "web": {
                "allocation": {
                    "personal_availability": [
                        {"person": "p1", "unit": "hours", "per_day": "6", "source": "entrevista"}
                    ]
                }
            }
        }
    }
    resolved = resolve_config(_document(), local_document=local)
    availability = resolved.config.team("web").allocation.personal_availability
    assert availability[0].per_day == Decimal("6")
    assert availability[0].source == "entrevista"
