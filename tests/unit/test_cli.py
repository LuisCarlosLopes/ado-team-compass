"""T01 — contrato mínimo da CLI: versão, códigos de saída e stdout/stderr separados."""

import json

import pytest

from ado_team_compass import __version__
from ado_team_compass.cli import COMMANDS, main
from ado_team_compass.errors import ExitCode


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


def test_unimplemented_command_error_payload(capsys):
    main(["forecast"])
    stderr = capsys.readouterr().err
    payload = json.loads(stderr[stderr.index("{") :])
    assert payload["error"]["code"] == "E_CMD_NAO_DISPONIVEL"
    assert payload["error"]["exit_code"] == int(ExitCode.INVALID_INPUT)


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
