"""Servidor MCP do motor: catálogo, envelope de resposta e montagem do argv.

O servidor não pode inventar regra nem abrir canal: ele traduz chamada de ferramenta em
entrada da CLI e devolve o resultado do motor com o contrato de saída preservado.
"""

from __future__ import annotations

import json

import pytest

from ado_team_compass.errors import ExitCode
from ado_team_compass.server import TOOLS, describe, envelope, run_command, tool_by_name
from ado_team_compass.server.app import RESULT_CHARACTER_LIMIT, build_server
from ado_team_compass.server.runner import UNEXPECTED_FAILURE, CommandResult

CLI_COMMANDS = {
    "version",
    "login",
    "logout",
    "doctor",
    "setup",
    "status",
    "history",
    "planning",
    "allocation",
    "evidence",
    "report",
    "render",
    "replay",
    "demo",
}


def test_every_tool_maps_to_a_real_cli_command():
    from ado_team_compass.cli import COMMANDS

    known = {command.name for command in COMMANDS}
    for tool in TOOLS:
        assert tool.command in known, f"{tool.name} aponta para entrada inexistente"


def test_the_catalog_covers_the_declared_commands():
    assert {tool.command for tool in TOOLS} == CLI_COMMANDS


def test_tool_names_are_prefixed_and_unique():
    names = [tool.name for tool in TOOLS]
    assert len(names) == len(set(names))
    assert all(name.startswith("atc_") for name in names)


def test_decisions_and_forecast_stay_out_of_the_catalog():
    """Entrada que exige arquivo humano ou premissa explícita não é decisão do assistente."""
    assert "decisions" not in {tool.command for tool in TOOLS}
    assert "forecast" not in {tool.command for tool in TOOLS}


def test_arguments_become_a_single_argv_element_per_option():
    tool = tool_by_name("atc_status")
    argv = tool.argv({"team": "squad-a", "format": "markdown"})
    assert argv[0] == "status"
    assert "--team=squad-a" in argv
    assert "--format=markdown" in argv


def test_a_value_that_looks_like_an_option_is_never_reinterpreted():
    """Valor com hífen fica colado à opção: o parser não o lê como outra entrada."""
    argv = tool_by_name("atc_status").argv({"team": "--offline"})
    assert "--offline" not in argv
    assert "--team=--offline" in argv


def test_boolean_options_appear_only_when_true():
    tool = tool_by_name("atc_status")
    assert "--with-history" in tool.argv({"with_history": True})
    assert "--with-history" not in tool.argv({"with_history": False})


def test_setup_is_always_non_interactive():
    """No host não há quem responda a uma pergunta do motor: ambiguidade vira erro."""
    assert "--non-interactive" in tool_by_name("atc_setup").argv({"organization": "contoso"})


def test_unknown_parameters_are_refused():
    with pytest.raises(ValueError, match="não aceitos"):
        tool_by_name("atc_demo").argv({"team": "squad-a"})


def test_unknown_tool_is_refused():
    with pytest.raises(ValueError, match="desconhecida"):
        tool_by_name("atc_delete_everything")


def test_input_schema_refuses_extra_properties():
    for tool in TOOLS:
        schema = tool.input_schema()
        assert schema["additionalProperties"] is False


def test_tools_that_reach_ado_are_marked_as_open_world():
    reaching = {tool.name for tool in TOOLS if tool.reaches_ado}
    assert reaching == {
        "atc_doctor",
        "atc_login",
        "atc_setup",
        "atc_status",
        "atc_history",
        "atc_planning",
    }
    for tool in TOOLS:
        descriptor = describe(tool)
        assert descriptor.annotations is not None
        assert descriptor.annotations.destructiveHint is False
        assert descriptor.annotations.openWorldHint is tool.reaches_ado


def test_the_envelope_preserves_the_exit_code_contract():
    tool = tool_by_name("atc_status")
    result = CommandResult(
        command="status", exit_code=int(ExitCode.ACCESS_DENIED), stdout="", stderr=""
    )
    payload = envelope(tool, result)
    assert payload["exit_code"] == 3
    assert "acesso insuficiente" in payload["exit_meaning"]


def test_a_partial_result_keeps_the_report_and_says_it_is_partial():
    tool = tool_by_name("atc_history")
    result = CommandResult(
        command="history",
        exit_code=int(ExitCode.PARTIAL_CAPABILITY),
        stdout=json.dumps({"history": None}),
        stderr="",
    )
    payload = envelope(tool, result)
    assert payload["result"] == {"history": None}
    assert "parcial" in payload["notice"]


def test_a_structured_error_from_the_engine_reaches_the_host():
    tool = tool_by_name("atc_status")
    error = {"code": "E_CFG_AUSENTE", "message": "sem configuração", "remediation": "rode setup"}
    result = CommandResult(
        command="status",
        exit_code=int(ExitCode.INVALID_INPUT),
        stdout="",
        stderr=json.dumps({"error": error}),
    )
    payload = envelope(tool, result)
    assert payload["error"]["code"] == "E_CFG_AUSENTE"
    assert "result" not in payload


def test_an_oversized_result_is_replaced_by_an_actionable_notice():
    tool = tool_by_name("atc_report")
    oversized = json.dumps({"items": ["x" * 40] * (RESULT_CHARACTER_LIMIT // 20)})
    result = CommandResult(command="report", exit_code=0, stdout=oversized, stderr="")
    payload = envelope(tool, result)
    assert "result" not in payload
    assert "output" in payload["result_omitted"]


def test_an_unexpected_failure_becomes_a_diagnostic_not_a_crash(monkeypatch):
    from ado_team_compass import cli

    def explode(_argv):
        raise RuntimeError("motor quebrou")

    monkeypatch.setattr(cli, "main", explode)
    result = run_command(["version"])
    assert result.exit_code == UNEXPECTED_FAILURE
    error = result.error()
    assert error is not None
    assert error["code"] == "E_FALHA_INESPERADA"


def test_the_runner_never_lets_engine_output_reach_the_real_stdout(capsys):
    """stdout é o canal do protocolo: a saída do motor precisa voltar capturada."""
    result = run_command(["version"])
    captured = capsys.readouterr()
    assert captured.out == ""
    assert result.payload()["name"] == "ado-team-compass"


def test_the_server_announces_the_whole_catalog_with_instructions():
    server = build_server()
    assert server.name == "ado-team-compass"
    assert "somente leitura" in (server.instructions or "")
    assert "não calcula métricas" in (server.instructions or "").lower()
