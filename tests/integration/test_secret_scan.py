"""T14 — verificação de segredos em artefatos, logs e diagnóstico."""

from __future__ import annotations

import json
import re
from datetime import datetime

import pytest

from ado_team_compass.adapters.ado_mcp import AdoMcpClient
from ado_team_compass.config import resolve_config
from ado_team_compass.demo import ORGANIZATION, demo_config_document, transport
from ado_team_compass.errors import AccessError, CompassError
from ado_team_compass.pipeline import execute_status
from ado_team_compass.runs import RunStore

AS_OF = datetime.fromisoformat("2026-09-15T12:00:00-03:00")
SECRET = "eyJhbGciOiJIUzI1NiJ9.SEGREDO.assinatura"

PATTERNS = (
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}"),  # JWT
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),  # token GitHub
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._-]{10,}"),
    re.compile(r"(?i)\b(pat|password|senha|client_secret)\s*[:=]\s*\S+"),
)


def _scan(text: str) -> list[str]:
    return [match.group(0) for pattern in PATTERNS for match in pattern.finditer(text)]


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    resolved = resolve_config(demo_config_document())
    client = AdoMcpClient(transport=transport())
    client.handshake()
    store = RunStore(tmp_path_factory.mktemp("runs"))
    outcome = execute_status(
        client,
        resolved.config.teams[0],
        organization=ORGANIZATION,
        as_of=AS_OF,
        store=store,
        resolved=resolved,
    )
    return outcome


def test_no_secret_like_value_appears_in_any_artifact(run):
    for path in sorted(run.run.directory.rglob("*")):
        if not path.is_file():
            continue
        findings = _scan(path.read_text(encoding="utf-8"))
        assert not findings, f"{path}: {findings}"


def test_effective_config_in_the_manifest_is_sanitized(run):
    payload = json.dumps(run.run.manifest.effective_config, ensure_ascii=False)
    assert "session_ref" not in payload or "token" not in payload
    assert _scan(payload) == []


def test_source_identity_is_opaque(run):
    assert run.run.manifest.source_identity.startswith("sha256:")
    assert ORGANIZATION not in run.run.manifest.source_identity


def test_transport_failure_message_does_not_leak_the_token(caplog):
    error = AccessError(
        "E_MCP_AUTENTICACAO",
        "sessão recusada",
        detail={"authorization": f"Bearer {SECRET}", "operation": "list_projects"},
    )
    rendered = json.dumps(error.as_dict(), ensure_ascii=False)
    assert SECRET not in rendered
    assert _scan(rendered) == []


def test_call_log_arguments_are_sanitized():
    client = AdoMcpClient(transport=transport())
    client.handshake()
    from ado_team_compass.adapters.ado_mcp import Operation

    client.call(Operation.LIST_PROJECTS, {"project": "demo", "access_token": SECRET})
    rendered = json.dumps(
        [record.arguments for record in client.call_log], ensure_ascii=False, default=str
    )
    assert SECRET not in rendered


def test_every_product_error_renders_without_secrets():
    error = CompassError(
        "E_X",
        "falha",
        detail={"client_secret": SECRET, "nested": {"pat": SECRET}, "path": "/tmp/x"},
    )
    rendered = json.dumps(error.as_dict(), ensure_ascii=False)
    assert SECRET not in rendered
    assert "/tmp/x" in rendered
