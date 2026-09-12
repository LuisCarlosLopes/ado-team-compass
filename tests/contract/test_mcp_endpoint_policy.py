"""T03 — política de endpoint: HTTPS, servidor remoto oficial e recusa de API direta."""

import pytest
from pydantic import ValidationError

from ado_team_compass.contracts.config import ConnectionConfig, McpServerConfig, McpTransport


def _connection(**server: object) -> ConnectionConfig:
    return ConnectionConfig(
        alias="contoso", organization="contoso", server=McpServerConfig(**server)
    )


def test_remote_official_server_is_the_default_transport():
    connection = _connection()
    assert connection.server.transport is McpTransport.HTTP
    assert connection.server.resolved_url("contoso") == "https://mcp.azuredevops.com/contoso/mcp"


def test_explicit_url_is_preserved():
    connection = _connection(url="https://mcp.azuredevops.com/outra/mcp")
    assert connection.server.resolved_url("contoso").endswith("/outra/mcp")


@pytest.mark.parametrize(
    "url",
    [
        "http://mcp.azuredevops.com/contoso/mcp",
        "https://dev.azure.com/contoso/_apis/wit/workitems",
        "https://analytics.dev.azure.com/contoso/_odata/v4.0-preview",
        "https://contoso.visualstudio.com/_apis/work/teamsettings",
    ],
)
def test_direct_or_insecure_endpoints_are_refused(url):
    with pytest.raises(ValidationError):
        _connection(url=url)


def test_stdio_alternative_still_requires_the_official_package_command():
    with pytest.raises(ValidationError):
        _connection(transport=McpTransport.STDIO)
    connection = _connection(
        transport=McpTransport.STDIO, command=("npx", "-y", "@azure-devops/mcp", "contoso")
    )
    assert "stdio" in str(connection.server.transport)
