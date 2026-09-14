"""Launcher do bundle: sobe o motor sem exigir instalação prévia da CLI.

O launcher é a peça que remove o pré-requisito manual. Ele só pode usar a biblioteca padrão —
roda antes de qualquer ambiente existir — e não pode escrever em stdout, que pertence ao
protocolo MCP.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml

ROOT = Path()
SHARED = ROOT / "integrations" / "shared"
DOCUMENT = yaml.safe_load((SHARED / "hosts.yaml").read_text(encoding="utf-8"))
HOSTS = DOCUMENT["hosts"]
SOURCE = SHARED / "launcher" / "atc-mcp.py"

#: Módulos que o launcher pode importar: tudo o que já vem com o Python.
STANDARD_LIBRARY = set(sys.stdlib_module_names)


def load(path: Path = SOURCE) -> ModuleType:
    spec = importlib.util.spec_from_file_location("atc_mcp_launcher", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_bundle_ships_the_launcher():
    for host in HOSTS.values():
        launcher = ROOT / str(host["bundle_dir"]) / str(DOCUMENT["launcher_path"])
        assert launcher.is_file(), f"bundle sem launcher: {launcher}"
        assert launcher.read_text(encoding="utf-8") == SOURCE.read_text(encoding="utf-8")


def test_the_launcher_only_uses_the_standard_library():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    assert imported <= STANDARD_LIBRARY, f"dependência externa no launcher: {imported}"


def test_the_launcher_never_writes_to_stdout():
    """stdout pertence ao protocolo MCP: uma linha solta ali corrompe a sessão."""
    text = SOURCE.read_text(encoding="utf-8")
    assert "sys.stdout" not in text
    calls = [
        node
        for node in ast.walk(ast.parse(text))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
    ]
    assert not calls, "o launcher não pode imprimir em stdout"


def test_an_explicit_interpreter_wins_over_everything_else(monkeypatch):
    monkeypatch.setenv("ADO_TEAM_COMPASS_ENGINE_PYTHON", "/opt/python/bin/python3")
    module = load()
    assert module.resolve() == ["/opt/python/bin/python3", "-m", "ado_team_compass.server"]


def test_an_engine_already_installed_is_preferred_over_bootstrap(monkeypatch, tmp_path):
    monkeypatch.delenv("ADO_TEAM_COMPASS_ENGINE_PYTHON", raising=False)
    module = load()
    monkeypatch.setattr(module, "serves_engine", lambda python: False)
    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/local/bin/ado-team-compass-mcp")
    monkeypatch.setattr(module, "bootstrap", _never_called)
    assert module.resolve() == ["/usr/local/bin/ado-team-compass-mcp"]


def test_without_engine_or_wheel_the_message_says_what_to_do(monkeypatch):
    monkeypatch.delenv("ADO_TEAM_COMPASS_ENGINE_PYTHON", raising=False)
    module = load()
    monkeypatch.setattr(module, "serves_engine", lambda python: False)
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    monkeypatch.setattr(module, "bundled_wheel", lambda: None)
    with pytest.raises(SystemExit, match="wheel embutido"):
        module.resolve()


def test_bootstrap_can_be_forbidden_by_the_operator(monkeypatch, tmp_path):
    wheel = tmp_path / "ado_team_compass-0.2.0-py3-none-any.whl"
    wheel.write_bytes(b"")
    monkeypatch.delenv("ADO_TEAM_COMPASS_ENGINE_PYTHON", raising=False)
    monkeypatch.setenv("ADO_TEAM_COMPASS_NO_BOOTSTRAP", "1")
    monkeypatch.setenv("ADO_TEAM_COMPASS_RUNTIME_HOME", str(tmp_path / "runtime"))
    module = load()
    monkeypatch.setattr(module, "serves_engine", lambda python: False)
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    monkeypatch.setattr(module, "bundled_wheel", lambda: wheel)
    monkeypatch.setattr(module, "bootstrap", _never_called)
    with pytest.raises(SystemExit, match="NO_BOOTSTRAP"):
        module.resolve()


def test_a_prepared_runtime_is_reused_instead_of_installing_again(monkeypatch, tmp_path):
    wheel = tmp_path / "ado_team_compass-0.2.0-py3-none-any.whl"
    wheel.write_bytes(b"")
    monkeypatch.delenv("ADO_TEAM_COMPASS_ENGINE_PYTHON", raising=False)
    monkeypatch.delenv("ADO_TEAM_COMPASS_NO_BOOTSTRAP", raising=False)
    monkeypatch.setenv("ADO_TEAM_COMPASS_RUNTIME_HOME", str(tmp_path / "runtime"))
    module = load()
    prepared = module.venv_python(tmp_path / "runtime" / "0.2.0")
    monkeypatch.setattr(module, "serves_engine", lambda python: Path(python) == prepared)
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    monkeypatch.setattr(module, "bundled_wheel", lambda: wheel)
    monkeypatch.setattr(module, "bootstrap", _never_called)
    assert module.resolve() == [str(prepared), "-m", "ado_team_compass.server"]


def _never_called(*args: object, **kwargs: object) -> object:
    raise AssertionError("o launcher não deveria preparar um ambiente novo aqui")


def test_a_newer_interpreter_is_found_when_the_host_starts_an_old_one(monkeypatch):
    """`python3` do sistema ainda é 3.9 em macOS: o launcher procura um compatível."""
    module = load()
    monkeypatch.setattr(
        module.shutil,
        "which",
        lambda name: f"/usr/local/bin/{name}" if name == "python3.13" else None,
    )
    monkeypatch.setattr(
        module, "interpreter_version", lambda python: (3, 13) if "3.13" in python else (3, 9)
    )
    assert module.compatible_interpreter() == "/usr/local/bin/python3.13"


def test_an_interpreter_below_the_minimum_is_never_chosen(monkeypatch):
    module = load()
    monkeypatch.setattr(module.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(module, "interpreter_version", lambda python: (3, 9))
    assert module.compatible_interpreter() is None


def test_without_a_compatible_interpreter_the_message_names_the_escape_hatch(monkeypatch):
    module = load()
    monkeypatch.setattr(module.sys, "version_info", (3, 9, 6))
    monkeypatch.setattr(module, "compatible_interpreter", lambda: None)
    monkeypatch.delenv("ADO_TEAM_COMPASS_LAUNCHER_REEXEC", raising=False)
    with pytest.raises(SystemExit, match="ADO_TEAM_COMPASS_ENGINE_PYTHON"):
        module.main()


def test_the_interpreter_swap_never_loops(monkeypatch):
    """Uma troca já aconteceu: insistir viraria laço de processos."""
    module = load()
    monkeypatch.setattr(module.sys, "version_info", (3, 9, 6))
    monkeypatch.setenv("ADO_TEAM_COMPASS_LAUNCHER_REEXEC", "1")
    with pytest.raises(SystemExit, match=r"3\.11 ou superior"):
        module.main()


def test_the_environment_is_created_by_subprocess_not_in_process():
    """Em processo, o macOS herda __PYVENV_LAUNCHER__ e o ensurepip do ambiente novo aborta."""
    text = SOURCE.read_text(encoding="utf-8")
    assert "EnvBuilder" not in text
    assert '"-m", "venv"' in text
