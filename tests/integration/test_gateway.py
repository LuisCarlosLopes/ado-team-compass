"""T28 — gateway autenticado de leitura. Cenários V27 e V28."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from ado_team_compass.adapters.ado_mcp import AdoMcpClient
from ado_team_compass.config import resolve_config
from ado_team_compass.demo import ORGANIZATION, demo_config_document
from ado_team_compass.demo.dataset import default_responses, transport
from ado_team_compass.gateway.app import create_app
from ado_team_compass.gateway.auth import (
    AccessControl,
    AuthError,
    OidcTokenVerifier,
    Principal,
    StaticTokenVerifier,
)
from ado_team_compass.gateway.store import ReportRepository
from ado_team_compass.pipeline import execute_status
from ado_team_compass.runs import RunStore

AS_OF = datetime.fromisoformat("2026-09-15T12:00:00-03:00")
NOW = AS_OF + timedelta(hours=2)

ANA = Principal(subject="ana@empresa.com", issuer="https://idp", audience="compass")
BRUNO = Principal(subject="bruno@empresa.com", issuer="https://idp", audience="compass")


@pytest.fixture
def environment(tmp_path: Path):
    resolved = resolve_config(demo_config_document())
    client = AdoMcpClient(transport=transport(default_responses()))
    client.handshake()
    store = RunStore(tmp_path / "runs")
    outcome = execute_status(
        client,
        resolved.config.teams[0],
        organization=ORGANIZATION,
        as_of=AS_OF,
        store=store,
        resolved=resolved,
    )
    acl = tmp_path / "acl.json"
    acl.write_text(
        json.dumps(
            {"organization": ORGANIZATION, "users": {ANA.subject: ["demo"], BRUNO.subject: []}}
        ),
        encoding="utf-8",
    )
    application = create_app(
        repository=ReportRepository(store=store),
        verifier=StaticTokenVerifier(principals={"token-ana": ANA, "token-bruno": BRUNO}),
        access=AccessControl(path=acl),
        clock=lambda: NOW,
    )
    return TestClient(application), outcome, acl, store


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_authorized_user_lists_only_its_teams(environment):
    client, *_ = environment
    response = client.get("/v1/teams", headers=_auth("token-ana"))
    assert response.status_code == 200
    assert response.json()["teams"] == ["demo"]


def test_report_matches_the_cli_numbers(environment):
    client, outcome, _, store = environment
    response = client.get("/v1/teams/demo/report", headers=_auth("token-ana"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == outcome.run.manifest.run_id
    served = {metric["id"]: metric for metric in payload["report"]["metrics"]}
    stored = {
        metric["id"]: metric
        for metric in store.load(outcome.run.manifest.run_id).artifact("metrics.json")["metrics"]
    }
    assert served["known_remaining_work"]["quantity"] == stored["known_remaining_work"]["quantity"]
    assert payload["state"] == outcome.run.manifest.state.value
    assert payload["partial_reasons"]
    assert "não acessa o Azure DevOps" in payload["disclaimer"]


# V27 — token ausente, expirado ou sem acesso.
def test_v27_missing_token_is_401_and_leaks_nothing(environment):
    client, *_ = environment
    for path in ("/v1/teams", "/v1/teams/demo/report"):
        response = client.get(path)
        assert response.status_code == 401
        assert "demo" not in response.text or path.endswith("report")
        assert "known_remaining_work" not in response.text


def test_v27_unknown_or_expired_token_is_401(environment):
    client, *_ = environment
    response = client.get("/v1/teams/demo/report", headers=_auth("token-expirado"))
    assert response.status_code == 401
    assert "known_remaining_work" not in response.text


def test_v27_valid_token_without_team_access_is_403(environment):
    client, *_ = environment
    response = client.get("/v1/teams/demo/report", headers=_auth("token-bruno"))
    assert response.status_code == 403
    assert "known_remaining_work" not in response.text


def test_v27_changing_the_run_id_does_not_bypass_the_acl(environment):
    client, outcome, *_ = environment
    response = client.get(
        f"/v1/runs/{outcome.run.manifest.run_id}/report", headers=_auth("token-bruno")
    )
    assert response.status_code == 403
    evidence = client.get(
        f"/v1/runs/{outcome.run.manifest.run_id}/evidence", headers=_auth("token-bruno")
    )
    assert evidence.status_code == 403


def test_v27_revoking_access_applies_on_the_next_request(environment):
    client, _, acl, _ = environment
    assert client.get("/v1/teams/demo/report", headers=_auth("token-ana")).status_code == 200
    acl.write_text(json.dumps({"users": {ANA.subject: []}}), encoding="utf-8")
    assert client.get("/v1/teams/demo/report", headers=_auth("token-ana")).status_code == 403


def test_v27_unknown_user_has_no_access_by_default(environment):
    client, _, acl, _ = environment
    acl.write_text(json.dumps({"users": {}}), encoding="utf-8")
    assert client.get("/v1/teams", headers=_auth("token-ana")).json()["teams"] == []
    assert client.get("/v1/teams/demo/report", headers=_auth("token-ana")).status_code == 403


# V28 — relatório antigo, inexistente ou grande.
def test_v28_missing_team_report_is_404(environment):
    client, _, acl, _ = environment
    acl.write_text(json.dumps({"users": {ANA.subject: ["inexistente"]}}), encoding="utf-8")
    response = client.get("/v1/teams/inexistente/report", headers=_auth("token-ana"))
    assert response.status_code == 404
    assert "não há relatório" in response.json()["detail"]


def test_v28_unknown_run_is_404(environment):
    client, *_ = environment
    assert (
        client.get("/v1/runs/20200101T000000-demo/report", headers=_auth("token-ana")).status_code
        == 404
    )


def test_v28_old_report_keeps_its_timestamp_and_warns(tmp_path):
    resolved = resolve_config(demo_config_document())
    client_mcp = AdoMcpClient(transport=transport(default_responses()))
    client_mcp.handshake()
    store = RunStore(tmp_path / "runs")
    outcome = execute_status(
        client_mcp,
        resolved.config.teams[0],
        organization=ORGANIZATION,
        as_of=AS_OF,
        store=store,
        resolved=resolved,
    )
    acl = tmp_path / "acl.json"
    acl.write_text(json.dumps({"users": {ANA.subject: ["demo"]}}), encoding="utf-8")
    application = create_app(
        repository=ReportRepository(store=store),
        verifier=StaticTokenVerifier(principals={"token-ana": ANA}),
        access=AccessControl(path=acl),
        clock=lambda: AS_OF + timedelta(days=3),
    )
    response = TestClient(application).get("/v1/teams/demo/report", headers=_auth("token-ana"))
    payload = response.json()
    assert payload["is_stale"] is True
    assert "não foram atualizados" in payload["staleness_note"]
    assert payload["as_of"] == AS_OF.isoformat()
    assert payload["run_id"] == outcome.run.manifest.run_id


def test_v28_evidence_is_paginated_and_bounded(environment):
    client, outcome, *_ = environment
    run_id = outcome.run.manifest.run_id
    first = client.get(
        f"/v1/runs/{run_id}/evidence", params={"limit": 3}, headers=_auth("token-ana")
    ).json()
    assert len(first["references"]) == 3
    assert first["next_cursor"] == 3
    second = client.get(
        f"/v1/runs/{run_id}/evidence",
        params={"limit": 3, "cursor": first["next_cursor"]},
        headers=_auth("token-ana"),
    ).json()
    assert set(second["references"]).isdisjoint(first["references"])
    too_big = client.get(
        f"/v1/runs/{run_id}/evidence", params={"limit": 5000}, headers=_auth("token-ana")
    )
    assert too_big.status_code == 422


def test_v28_single_evidence_returns_the_minimized_record(environment):
    client, outcome, *_ = environment
    response = client.get(
        f"/v1/runs/{outcome.run.manifest.run_id}/evidence",
        params={"reference": "101"},
        headers=_auth("token-ana"),
    )
    assert response.status_code == 200
    evidence = response.json()["evidence"]
    assert evidence["remaining_work"] == {"value": "10", "unit": "hours"}
    assert "description" not in evidence


def test_evidence_reference_cannot_escape_the_run_directory(environment):
    client, outcome, *_ = environment
    response = client.get(
        f"/v1/runs/{outcome.run.manifest.run_id}/evidence",
        params={"reference": "../../run"},
        headers=_auth("token-ana"),
    )
    assert response.status_code in (404, 422)


def test_only_get_methods_are_exposed(environment):
    client, *_ = environment
    for method in ("post", "put", "patch", "delete"):
        response = getattr(client, method)("/v1/teams/demo/report", headers=_auth("token-ana"))
        assert response.status_code == 405


def test_health_endpoint_does_not_expose_team_data(environment):
    client, *_ = environment
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_oidc_verifier_requires_a_valid_token():
    verifier = OidcTokenVerifier(
        issuer="https://idp", audience="compass", jwks_url="https://idp/jwks"
    )
    with pytest.raises(AuthError):
        verifier.verify("token-invalido")


def test_openapi_document_declares_oauth_and_only_get_operations():
    from ado_team_compass.gateway.schema import build_openapi

    document = build_openapi()
    assert document["security"] == [{"oauth2": ["reports.read"]}]
    assert "oauth2" in document["components"]["securitySchemes"]
    for path, operations in document["paths"].items():
        assert set(operations) == {"get"}, path
