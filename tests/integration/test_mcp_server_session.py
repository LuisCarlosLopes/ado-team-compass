"""Sessão MCP real contra o servidor do motor, do anúncio de ferramentas à resposta.

Exercita o caminho que o host de IA percorre: listar ferramentas, chamar uma delas e receber
o resultado do motor. Nenhuma rede e nenhuma credencial: a demonstração usa o conjunto
sintético do pacote.
"""

from __future__ import annotations

import anyio
import pytest
from mcp.shared.memory import create_connected_server_and_client_session as connected

from ado_team_compass.server import TOOLS
from ado_team_compass.server.app import build_server


def drive(scenario):
    """Roda o cenário assíncrono contra uma sessão conectada em memória."""

    async def run():
        async with connected(build_server()) as client:
            return await scenario(client)

    return anyio.run(run)


def test_the_host_sees_every_tool_with_a_usable_schema():
    async def scenario(client):
        return await client.list_tools()

    listing = drive(scenario)
    assert {tool.name for tool in listing.tools} == {tool.name for tool in TOOLS}
    for tool in listing.tools:
        assert tool.description
        assert tool.inputSchema["type"] == "object"


def test_version_answers_through_the_protocol():
    async def scenario(client):
        return await client.call_tool("atc_version", {})

    result = drive(scenario)
    payload = result.structuredContent or {}
    assert payload["exit_code"] == 0
    assert payload["result"]["name"] == "ado-team-compass"


def test_demo_produces_the_synthetic_report_without_network_or_credentials(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    async def scenario(client):
        return await client.call_tool("atc_demo", {"format": "markdown"})

    payload = drive(scenario).structuredContent or {}
    assert payload["exit_code"] in (0, 5)
    assert "Situação atual" in payload["result"]


def test_a_missing_configuration_comes_back_as_a_diagnosis_not_an_exception(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    async def scenario(client):
        return await client.call_tool("atc_status", {"team": "inexistente"})

    payload = drive(scenario).structuredContent or {}
    assert payload["exit_code"] == 2
    assert payload["error"]["code"].startswith("E_")
    assert payload["error"]["remediation"]


def test_an_argument_outside_the_schema_is_refused_before_the_engine_runs():
    async def scenario(client):
        return await client.call_tool("atc_demo", {"team": "squad-a"})

    result = drive(scenario)
    assert result.isError
    assert "validation" in str(result.content[0].text).lower()


@pytest.mark.parametrize("tool_name", ["atc_status", "atc_history", "atc_planning"])
def test_collection_tools_are_announced_as_reaching_an_external_system(tool_name):
    async def scenario(client):
        return await client.list_tools()

    listing = drive(scenario)
    tool = next(entry for entry in listing.tools if entry.name == tool_name)
    assert tool.annotations is not None
    assert tool.annotations.openWorldHint is True
    assert tool.annotations.destructiveHint is False
