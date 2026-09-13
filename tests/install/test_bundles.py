"""T13, T26 e T27 — bundles locais gerados da fonte comum. V25 e V26."""

import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path()
SHARED = ROOT / "integrations" / "shared"
HOSTS = yaml.safe_load((SHARED / "hosts.yaml").read_text(encoding="utf-8"))["hosts"]
SKILL_NAMES = sorted(
    path.stem for path in (SHARED / "skills").glob("*.md") if path.stem != "common"
)

FOREIGN = {
    "claude": ("ANTIGRAVITY_", "CODEX_", "CURSOR_", ".codex-plugin", ".cursor-plugin"),
    "antigravity": (
        "CLAUDE_PLUGIN_ROOT",
        "CODEX_",
        "CURSOR_",
        ".claude-plugin",
        ".codex-plugin",
        ".cursor-plugin",
    ),
    "codex": ("CLAUDE_PLUGIN_ROOT", "ANTIGRAVITY_", "CURSOR_", ".claude-plugin", ".cursor-plugin"),
    "cursor": (
        "CLAUDE_PLUGIN_ROOT",
        "ANTIGRAVITY_",
        "CODEX_",
        ".claude-plugin",
        ".codex-plugin",
    ),
}


def _bundle(host_key: str) -> Path:
    return ROOT / str(HOSTS[host_key]["bundle_dir"])


def _skill(host_key: str, name: str) -> str:
    host = HOSTS[host_key]
    path = _bundle(host_key) / str(host["skills_dir"]) / name / str(host["skill_file"])
    return path.read_text(encoding="utf-8")


def test_generated_bundles_are_up_to_date_with_the_shared_source():
    from packaging.build_bundles import build

    assert build(check=True) == 0, "rode python packaging/build_bundles.py"


@pytest.mark.parametrize("host_key", sorted(HOSTS))
def test_each_host_has_its_own_manifest_format(host_key):
    manifest_path = _bundle(host_key) / str(HOSTS[host_key]["manifest_path"])
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["name"] == "ado-team-compass"
    assert "description" in manifest
    if host_key == "antigravity":
        assert "requirements" not in manifest
        assert "skills" not in manifest
        assert "author" not in manifest
        assert "keywords" not in manifest
    else:
        assert manifest["requirements"]["mcp_server"].startswith("azure-devops")
        assert sorted(entry.split("/")[-1] for entry in manifest["skills"]) == SKILL_NAMES


def test_antigravity_manifest_is_cli_safe_minimal():
    manifest = json.loads((ROOT / "plugin/antigravity/plugin.json").read_text(encoding="utf-8"))
    assert set(manifest.keys()) == {"name", "description"}


def test_claude_manifest_lives_in_the_claude_plugin_directory():
    assert (ROOT / "plugin/claude/.claude-plugin/plugin.json").is_file()
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text("utf-8"))
    assert marketplace["plugins"][0]["source"] == "./plugin/claude"


def test_antigravity_manifest_lives_at_the_bundle_root():
    assert (ROOT / "plugin/antigravity/plugin.json").is_file()


def test_codex_manifest_has_its_own_directory():
    assert (ROOT / "plugin/codex/.codex-plugin/plugin.json").is_file()


def test_cursor_manifest_lives_in_cursor_plugin_directory():
    assert (ROOT / "plugin/cursor/.cursor-plugin/plugin.json").is_file()


# V26 — nenhuma variável ou sintaxe exclusiva de outro host vaza para o bundle.
@pytest.mark.parametrize("host_key", sorted(HOSTS))
def test_v26_no_foreign_host_marker_leaks_into_a_bundle(host_key):
    for path in _bundle(host_key).rglob("*"):
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        for marker in FOREIGN[host_key]:
            assert marker not in content, f"{path} contém {marker}"


@pytest.mark.parametrize("host_key", sorted(HOSTS))
def test_v26_bundles_are_self_contained(host_key):
    """Nenhuma skill referencia caminho fora do diretório instalado."""
    for name in SKILL_NAMES:
        content = _skill(host_key, name)
        assert "../" not in content
        assert "/Users/" not in content and "C:\\" not in content
        assert "integrations/shared" not in content


# V25 — mesma fixture, mesmas regras de métrica em todos os hosts.
def test_v25_metric_rules_are_identical_across_hosts():
    for name in SKILL_NAMES:
        bodies = {host_key: _skill(host_key, name).split("## Ambiente (")[0] for host_key in HOSTS}
        assert len(set(bodies.values())) == 1, f"a skill {name} divergiu entre hosts"


def test_v25_every_skill_repeats_the_shared_guardrails():
    for host_key in HOSTS:
        for name in SKILL_NAMES:
            content = _skill(host_key, name)
            assert "servidor MCP oficial da Microsoft" in content
            assert "Ausência de registro não é ociosidade" in content
            assert "Você não calcula métricas" in content


def test_skills_declare_name_and_description_front_matter():
    for host_key in HOSTS:
        for name in SKILL_NAMES:
            content = _skill(host_key, name)
            assert content.startswith("---\n")
            front_matter = content.split("---", 2)[1]
            metadata = yaml.safe_load(front_matter)
            assert metadata["name"].startswith("atc-")
            assert metadata["name"] == name
            assert len(metadata["description"]) > 40


def test_skills_use_the_installed_engine_not_the_development_tree():
    for host_key in HOSTS:
        for name in SKILL_NAMES:
            content = _skill(host_key, name)
            assert "python -m ado_team_compass" not in content
            assert "uv run" not in content
            for command in re.findall(r"^ado-team-compass .*$", content, re.MULTILINE):
                assert "src/" not in command


def test_collection_requires_mcp_and_offline_entries_are_declared():
    content = " ".join(_skill("claude", "atc-status").split())
    assert "Sem MCP oficial conectado, funcionam apenas" in content
    for entrada in ("`demo`", "`replay`", "`report`", "`render`", "`evidence`"):
        assert entrada in content


def test_host_notes_are_specific_to_each_host():
    assert "Claude Code" in _skill("claude", "atc-doctor")
    assert "Antigravity" in _skill("antigravity", "atc-doctor")
    assert "Codex" in _skill("codex", "atc-doctor")
    assert "Cursor" in _skill("cursor", "atc-doctor")
    assert "Antigravity" not in _skill("claude", "atc-doctor")
    assert "Claude Code" not in _skill("cursor", "atc-doctor")


def test_bundle_readme_documents_installation_and_limits():
    for host_key in HOSTS:
        readme = (_bundle(host_key) / "README.md").read_text(encoding="utf-8")
        assert "pip install ado-team-compass==" in readme
        assert "Somente leitura" in readme
        assert "precisa ser verificada em instalação real" in readme
