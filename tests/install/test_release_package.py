"""T15 — pacote de release: bundle, motor embutido e instruções de atualização/rollback."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from packaging.package_bundles import package_all, package_bundle

HOSTS = ("antigravity", "claude", "codex", "cursor")


@pytest.fixture
def fake_engine(tmp_path: Path) -> tuple[Path, Path]:
    wheel = tmp_path / "ado_team_compass-0.3.0-py3-none-any.whl"
    wheel.write_bytes(b"wheel sintetico")
    lock = tmp_path / "uv.lock"
    lock.write_text("# lock sintético\n", encoding="utf-8")
    return wheel, lock


def test_every_host_produces_a_package_with_engine_and_lock(fake_engine, tmp_path):
    wheel, lock = fake_engine
    packages = package_all(wheel=wheel, lock=lock, version="0.3.0", output_dir=tmp_path / "dist")
    assert len(packages) == len(HOSTS)
    for package in packages:
        with zipfile.ZipFile(package) as archive:
            names = set(archive.namelist())
        assert f"engine/{wheel.name}" in names
        assert "engine/uv.lock" in names
        assert "INSTALL.md" in names
        assert any(name.endswith("SKILL.md") for name in names)


@pytest.mark.parametrize("host_key", HOSTS)
def test_package_carries_the_manifest_of_its_own_host(fake_engine, tmp_path, host_key):
    wheel, lock = fake_engine
    package = package_bundle(host_key, wheel=wheel, lock=lock, version="0.3.0", output_dir=tmp_path)
    with zipfile.ZipFile(package) as archive:
        names = set(archive.namelist())
        install = archive.read("INSTALL.md").decode("utf-8")
    expected = {
        "claude": ".claude-plugin/plugin.json",
        "antigravity": "plugin.json",
        "codex": ".codex-plugin/plugin.json",
        "cursor": ".cursor-plugin/plugin.json",
    }[host_key]
    assert expected in names
    assert "python -m pip install engine/" in install
    assert "somente leitura" in install


def test_install_notes_explain_update_rollback_and_data_preservation(fake_engine, tmp_path):
    wheel, lock = fake_engine
    package = package_bundle("claude", wheel=wheel, lock=lock, version="0.3.0", output_dir=tmp_path)
    with zipfile.ZipFile(package) as archive:
        install = archive.read("INSTALL.md").decode("utf-8")
    assert "Atualização e remoção" in install
    assert ".ado-team-compass/" in install
    assert "reinstale o pacote antigo" in install


def test_package_does_not_carry_local_run_data(fake_engine, tmp_path):
    wheel, lock = fake_engine
    package = package_bundle("claude", wheel=wheel, lock=lock, version="0.3.0", output_dir=tmp_path)
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
    assert not [name for name in names if ".ado-team-compass" in name]
    assert not [name for name in names if name.endswith(("run.json", "facts.json"))]
