"""T01 — erros com código estável, saída mapeada e detalhe sanitizado."""

import pytest

from ado_team_compass.errors import (
    AccessError,
    CollectError,
    CompassError,
    ConfigError,
    ExitCode,
    PartialResult,
    SchemaVersionError,
    sanitize_detail,
)


@pytest.mark.parametrize(
    ("error_type", "expected"),
    [
        (ConfigError, ExitCode.INVALID_INPUT),
        (AccessError, ExitCode.ACCESS_DENIED),
        (CollectError, ExitCode.COLLECT_FAILED),
        (PartialResult, ExitCode.PARTIAL_CAPABILITY),
        (SchemaVersionError, ExitCode.SCHEMA_INCOMPATIBLE),
    ],
)
def test_exit_code_mapping(error_type, expected):
    assert error_type("E_X", "mensagem").exit_code == expected


def test_detail_is_sanitized_recursively():
    error = CompassError(
        "E_X",
        "mensagem",
        detail={
            "org": "contoso",
            "access_token": "abc",
            "session": {"Authorization": "Bearer abc", "transport": "stdio"},
            "items": [{"pat": "xyz", "id": 7}],
        },
    )
    assert error.detail == {
        "org": "contoso",
        "access_token": "[redigido]",
        "session": {"Authorization": "[redigido]", "transport": "stdio"},
        "items": [{"pat": "[redigido]", "id": 7}],
    }


def test_sanitize_detail_accepts_none():
    assert sanitize_detail(None) == {}


def test_str_includes_code_and_remediation():
    error = ConfigError("E_CFG", "Configuração inválida.", remediation="Informe --team.")
    assert str(error) == "[E_CFG] Configuração inválida. Ação: Informe --team."
