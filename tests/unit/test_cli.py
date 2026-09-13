"""T01 — contrato mínimo da CLI: versão, códigos de saída e stdout/stderr separados."""

import argparse
import json

import pytest

from ado_team_compass import __version__
from ado_team_compass.cli import COMMANDS, main
from ado_team_compass.errors import ConfigError, ExitCode


def test_version_command_emits_json_on_stdout(capsys):
    assert main(["version"]) == int(ExitCode.OK)
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"name": "ado-team-compass", "version": __version__}


def test_version_flag_prints_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == __version__


def test_no_command_returns_invalid_input_and_writes_help_to_stderr(capsys):
    assert main([]) == int(ExitCode.INVALID_INPUT)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "ado-team-compass" in captured.err


def test_every_catalogued_command_has_a_handler():
    assert all(command.handler is not None for command in COMMANDS)


def test_unimplemented_command_reports_its_release(capsys):
    """O aviso de entrada ainda não disponível continua válido para releases futuras."""
    from ado_team_compass.cli import _Command, _not_implemented

    command = _Command("futuro", "Entrada futura", "v9.9", None)
    with pytest.raises(ConfigError) as error:
        _not_implemented(command)(argparse.Namespace())
    assert error.value.code == "E_CMD_NAO_DISPONIVEL"
    assert error.value.detail["release"] == "v9.9"
    assert error.value.exit_code == ExitCode.INVALID_INPUT


def test_output_option_writes_file_instead_of_stdout(tmp_path, capsys):
    destination = tmp_path / "nested" / "version.json"
    assert main(["version", "--output", str(destination)]) == int(ExitCode.OK)
    assert capsys.readouterr().out == ""
    assert json.loads(destination.read_text(encoding="utf-8"))["version"] == __version__


def test_command_catalog_covers_planned_entries():
    names = {command.name for command in COMMANDS}
    assert {
        "setup",
        "doctor",
        "collect",
        "report",
        "status",
        "allocation",
        "evidence",
        "replay",
        "demo",
        "render",
        "decisions",
        "history",
        "planning",
        "run-scheduled",
        "forecast",
    } <= names


def test_cli_demo_is_idempotent_and_can_be_executed_multiple_times(tmp_path, capsys):
    """Garante que rodar demo sucessivas vezes não falha por execução já existente."""
    demo_dir = tmp_path / "demo_store"
    # Primeira execução
    code1 = main(["demo", "--format", "markdown", "--output", str(demo_dir)])
    assert code1 == int(ExitCode.PARTIAL_CAPABILITY)
    out1 = capsys.readouterr().out
    assert "Situação atual — demo" in out1

    # Segunda execução imediata no mesmo diretório
    code2 = main(["demo", "--format", "markdown", "--output", str(demo_dir)])
    assert code2 == int(ExitCode.PARTIAL_CAPABILITY)
    out2 = capsys.readouterr().out
    assert "Situação atual — demo" in out2


def test_cli_demo_outputs_html_file(tmp_path, capsys):
    """Garante que a opção --output com arquivo .html grava o relatório HTML corretamente."""
    html_target = tmp_path / "output" / "relatorio-demo.html"
    code = main(["demo", "--format", "html", "--output", str(html_target)])
    assert code == int(ExitCode.PARTIAL_CAPABILITY)
    assert capsys.readouterr().out == ""
    assert html_target.is_file()
    content = html_target.read_text(encoding="utf-8")
    assert "<!doctype html>" in content
    assert "Situação atual — demo" in content


def test_cli_supports_python_m_execution():
    """Garante que o módulo __main__ pode ser importado e expõe o ponto de entrada."""
    import ado_team_compass.__main__ as main_module

    assert callable(main_module.main)
