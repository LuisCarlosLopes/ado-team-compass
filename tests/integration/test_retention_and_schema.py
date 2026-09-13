"""T14 — retenção de 30 dias, compatibilidade de schema e replay verificado."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from ado_team_compass.adapters.ado_mcp import AdoMcpClient
from ado_team_compass.config import resolve_config
from ado_team_compass.contracts.common import SCHEMA_MAJOR
from ado_team_compass.demo import ORGANIZATION, demo_config_document, transport
from ado_team_compass.errors import SchemaVersionError
from ado_team_compass.pipeline import execute_status, replay_run
from ado_team_compass.runs import RunStore
from ado_team_compass.schemas import CONTRACTS, export_schemas

AS_OF = datetime.fromisoformat("2026-09-15T12:00:00-03:00")


def _execute(store: RunStore, as_of: datetime):
    resolved = resolve_config(demo_config_document())
    client = AdoMcpClient(transport=transport())
    client.handshake()
    return (
        execute_status(
            client,
            resolved.config.teams[0],
            organization=ORGANIZATION,
            as_of=as_of,
            store=store,
            resolved=resolved,
        ),
        resolved,
    )


def test_retention_of_thirty_days_removes_only_old_runs(tmp_path):
    store = RunStore(tmp_path / "runs")
    old, _ = _execute(store, AS_OF - timedelta(days=45))
    recent, _ = _execute(store, AS_OF)
    removed = store.purge(now=AS_OF, retention_days=30)
    assert removed == (old.run.manifest.run_id,)
    assert store.list_runs() == (recent.run.manifest.run_id,)
    assert not old.run.directory.exists()
    assert store.load(recent.run.manifest.run_id).verify() == ()


def test_replay_is_verified_after_retention(tmp_path):
    store = RunStore(tmp_path / "runs")
    outcome, resolved = _execute(store, AS_OF)
    store.purge(now=AS_OF, retention_days=30)
    _, identical = replay_run(store, outcome.run.manifest.run_id, resolved=resolved)
    assert identical


def test_future_schema_major_is_refused_with_migration_message(tmp_path):
    store = RunStore(tmp_path / "runs")
    outcome, _ = _execute(store, AS_OF)
    manifest = outcome.run.directory / "run.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["schema_version"]["major"] = SCHEMA_MAJOR + 1
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SchemaVersionError) as error:
        store.load(outcome.run.manifest.run_id)
    assert "compatível" in str(error.value)


def test_exported_schemas_cover_every_contract(tmp_path):
    written = export_schemas(tmp_path / "schemas")
    assert len(written) == len(CONTRACTS)
    for path in written:
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert schema["x-schema-major"] == SCHEMA_MAJOR
        assert schema["$id"].endswith(f"{path.name.split('.')[0]}.json")


def test_artifacts_of_a_run_validate_against_their_contracts(tmp_path):
    from ado_team_compass.contracts.facts import FactSet
    from ado_team_compass.contracts.metrics import MetricSet, Summary
    from ado_team_compass.contracts.report import TeamReport

    store = RunStore(tmp_path / "runs")
    outcome, _ = _execute(store, AS_OF)
    run = store.load(outcome.run.manifest.run_id)
    assert FactSet.model_validate(run.artifact("facts.json"))
    assert MetricSet.model_validate(run.artifact("metrics.json"))
    assert Summary.model_validate(run.artifact("summary.json"))
    assert TeamReport.model_validate(run.artifact("report.json"))
