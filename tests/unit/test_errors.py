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
    extract_compass_error,
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


def test_extract_compass_error_direct():
    """Extração direta de CompassError sem encapsulamento."""
    error = ConfigError("E_TEST", "Erro direto")
    assert extract_compass_error(error) is error


def test_extract_compass_error_from_exception_group():
    """Extração recursiva de CompassError de dentro de ExceptionGroup."""
    error = ConfigError("E_TEST", "Erro no grupo")
    group = ExceptionGroup("tarefas", [ValueError("outro"), error])
    assert extract_compass_error(group) is error

    # Grupo aninhado
    nested_group = ExceptionGroup("raiz", [ExceptionGroup("sub", [error])])
    assert extract_compass_error(nested_group) is error


def test_extract_compass_error_returns_none_when_absent():
    """Retorna None quando não há CompassError presente."""
    assert extract_compass_error(ValueError("sem compass")) is None
    group = ExceptionGroup("grupo", [RuntimeError("erro"), KeyError("k")])
    assert extract_compass_error(group) is None
