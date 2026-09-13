"""Testes unitários para o gerenciamento de exceções em OfficialMcpTransport."""

from __future__ import annotations

import pytest

from ado_team_compass.contracts.config import ConnectionConfig, McpServerConfig
from ado_team_compass.errors import ConfigError
from ado_team_compass.mcp.session.official import OfficialMcpTransport


def _connection() -> ConnectionConfig:
    return ConnectionConfig(alias="test", organization="test", server=McpServerConfig())


def test_transport_exit_unwraps_exception_group_when_original_present() -> None:
    """Garante que OfficialMcpTransport.__exit__ desempacota o erro original."""
    transport = OfficialMcpTransport(_connection())
    original_error = ConfigError("E_TEST", "Erro original de teste")

    class FakeSessionCm:
        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            # Simula AnyIO levantando ExceptionGroup contendo o erro original
            raise ExceptionGroup("anyio taskgroup", [original_error])

    class FakePortalCm:
        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            pass

    transport._session_cm = FakeSessionCm()
    transport._portal_cm = FakePortalCm()

    with pytest.raises(ConfigError) as exc_info:
        transport.__exit__(type(original_error), original_error, None)

    assert exc_info.value is original_error


def test_transport_exit_raises_unrelated_exception_group() -> None:
    """Garante que OfficialMcpTransport.__exit__ preserva ExceptionGroup não relacionado ao erro."""
    transport = OfficialMcpTransport(_connection())
    original_error = ValueError("outro erro")
    unrelated_error = RuntimeError("falha no mcp")

    class FakeSessionCm:
        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            raise ExceptionGroup("anyio taskgroup", [unrelated_error])

    class FakePortalCm:
        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            pass

    transport._session_cm = FakeSessionCm()
    transport._portal_cm = FakePortalCm()

    with pytest.raises(ExceptionGroup) as exc_info:
        transport.__exit__(type(original_error), original_error, None)

    assert unrelated_error in exc_info.value.exceptions
