"""T06 — execuções imutáveis, cache isolado, evidência minimizada e retenção."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from ado_team_compass.contracts.common import Provenance, Quantity
from ado_team_compass.contracts.config import StateCategory
from ado_team_compass.contracts.facts import WorkItemFact
from ado_team_compass.contracts.run import RunState
from ado_team_compass.errors import ConfigError, ExitCode, SchemaVersionError
from ado_team_compass.runs import CacheKey, CollectionCache, RunStore, minimize_item
from ado_team_compass.runs.evidence import write_evidence
from ado_team_compass.runs.store import hash_payload, run_id_for

AS_OF = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
PROVENANCE = Provenance(source="mcp", tool="get_work_items_batch", collected_at=AS_OF)


def _item(item_id: int = 101, *, title: str | None = "Ajustar coleta") -> WorkItemFact:
    return WorkItemFact(
        id=item_id,
        organization="contoso",
        project_id="p1",
        item_type="Task",
        state="Committed",
        state_category=StateCategory.IN_PROGRESS,
        title=title,
        assigned_to="person-ana",
        remaining_work=Quantity(value=Decimal(10), unit="hours"),
        provenance=PROVENANCE,
    )


def _store(tmp_path: Path) -> RunStore:
    return RunStore(tmp_path / "runs")


def _finalize(store: RunStore, directory: Path, run_id: str, **overrides):
    payload: dict[str, object] = {
        "run_id": run_id,
        "state": RunState.COMPLETE,
        "source_identity": "sha256:opaco",
        "collection_started_at": AS_OF,
        "collection_finished_at": AS_OF,
        "as_of": AS_OF,
        "effective_config": {"teams": [{"alias": "core"}]},
        "artifact_hashes": {},
    }
    payload.update(overrides)
    return store.finalize(directory, **payload)  # type: ignore[arg-type]


def test_run_is_written_atomically_and_is_readable(tmp_path):
    store = _store(tmp_path)
    run_id = run_id_for(AS_OF, "core")
    directory = store.begin(run_id)
    facts_hash = store.write_json(directory, "facts.json", {"items": [101]})
    run = _finalize(store, directory, run_id, artifact_hashes={"facts.json": facts_hash})
    assert run.manifest.state is RunState.COMPLETE
    assert run.manifest.engine_version
    assert store.load(run_id).artifact("facts.json") == {"items": [101]}
    assert run.verify() == ()
    # Nenhum arquivo temporário permanece no diretório da execução.
    assert not list(directory.glob("*.tmp"))


def test_existing_run_is_never_overwritten(tmp_path):
    store = _store(tmp_path)
    run_id = run_id_for(AS_OF, "core")
    store.begin(run_id)
    with pytest.raises(ConfigError) as error:
        store.begin(run_id)
    assert error.value.code == "E_RUN_JA_EXISTE"


def test_partial_sources_cannot_be_marked_complete(tmp_path):
    store = _store(tmp_path)
    run_id = run_id_for(AS_OF, "core")
    directory = store.begin(run_id)
    with pytest.raises(ConfigError) as error:
        _finalize(store, directory, run_id, partial_reasons=("capacidade indisponível",))
    assert error.value.code == "E_RUN_ESTADO_INCONSISTENTE"


def test_partial_run_is_valid_when_declared_partial(tmp_path):
    store = _store(tmp_path)
    run_id = run_id_for(AS_OF, "core")
    directory = store.begin(run_id)
    run = _finalize(
        store,
        directory,
        run_id,
        state=RunState.PARTIAL,
        partial_reasons=("capacity",),
    )
    assert run.manifest.state is RunState.PARTIAL
    assert run.manifest.partial_reasons == ("capacity",)


def test_interrupted_run_has_no_manifest_and_is_not_loadable(tmp_path):
    store = _store(tmp_path)
    run_id = run_id_for(AS_OF, "core")
    directory = store.begin(run_id)
    store.write_json(directory, "facts.json", {"items": []})
    store.abandon(directory, "falha de transporte na hidratação")
    with pytest.raises(ConfigError) as error:
        store.load(run_id)
    assert error.value.code == "E_RUN_NAO_ENCONTRADA"
    assert (directory / "INCOMPLETA.txt").is_file()
    assert store.list_runs() == ()


def test_previous_valid_run_survives_a_later_failure(tmp_path):
    store = _store(tmp_path)
    first_id = run_id_for(AS_OF, "core")
    directory = store.begin(first_id)
    _finalize(store, directory, first_id)
    second_id = run_id_for(AS_OF + timedelta(hours=1), "core")
    store.abandon(store.begin(second_id), "interrompida")
    assert store.list_runs() == (first_id,)
    latest = store.latest("core")
    assert latest is not None
    assert latest.manifest.run_id == first_id


def test_tampered_artifact_is_detected_by_the_recorded_hash(tmp_path):
    store = _store(tmp_path)
    run_id = run_id_for(AS_OF, "core")
    directory = store.begin(run_id)
    facts_hash = store.write_json(directory, "facts.json", {"items": [101]})
    run = _finalize(store, directory, run_id, artifact_hashes={"facts.json": facts_hash})
    assert run.verify() == ()
    (directory / "facts.json").write_text('{"items": [999]}', encoding="utf-8")
    assert store.load(run_id).verify() == ("facts.json",)


def test_incompatible_run_schema_is_reported(tmp_path):
    store = _store(tmp_path)
    run_id = run_id_for(AS_OF, "core")
    directory = store.begin(run_id)
    _finalize(store, directory, run_id)
    manifest_path = directory / "run.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["schema_version"]["major"] = 9
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SchemaVersionError) as error:
        store.load(run_id)
    assert error.value.exit_code == ExitCode.SCHEMA_INCOMPATIBLE


def test_retention_removes_old_runs_and_keeps_recent_ones(tmp_path):
    store = _store(tmp_path)
    old_as_of = AS_OF - timedelta(days=45)
    old_id = run_id_for(old_as_of, "core")
    _finalize(
        store,
        store.begin(old_id),
        old_id,
        as_of=old_as_of,
        collection_started_at=old_as_of,
        collection_finished_at=old_as_of,
    )
    recent_id = run_id_for(AS_OF, "core")
    _finalize(store, store.begin(recent_id), recent_id)
    removed = store.purge(now=AS_OF, retention_days=30)
    assert removed == (old_id,)
    assert store.list_runs() == (recent_id,)


def test_missing_artifact_is_actionable(tmp_path):
    store = _store(tmp_path)
    run_id = run_id_for(AS_OF, "core")
    run = _finalize(store, store.begin(run_id), run_id)
    with pytest.raises(ConfigError) as error:
        run.artifact("metrics.json")
    assert error.value.code == "E_RUN_ARTEFATO_AUSENTE"


# -- evidência ----------------------------------------------------------------------
def test_evidence_explains_a_total_without_full_description_or_credentials(tmp_path):
    store = _store(tmp_path)
    run_id = run_id_for(AS_OF, "core")
    directory = store.begin(run_id)
    references = write_evidence(directory, [_item()])
    assert references["101"] == "evidence/items/101.json"
    payload = json.loads((directory / references["101"]).read_text(encoding="utf-8"))
    assert payload["remaining_work"] == {"value": "10", "unit": "hours"}
    assert payload["provenance"]["tool"] == "get_work_items_batch"
    assert "description" not in payload
    assert "token" not in json.dumps(payload).lower()


def test_long_titles_are_truncated_and_control_characters_removed():
    payload = minimize_item(_item(title="a" * 200 + "\n\x00b"))
    excerpt = payload["title_excerpt"]
    assert len(excerpt) == 80
    assert "\x00" not in excerpt and "\n" not in excerpt


def test_absent_values_stay_absent_in_evidence():
    item = _item().model_copy(update={"remaining_work": None, "title": None})
    payload = minimize_item(item)
    assert payload["remaining_work"] is None
    assert payload["title_excerpt"] is None


# -- cache --------------------------------------------------------------------------
def _key(**overrides) -> CacheKey:
    base: dict[str, object] = {
        "organization": "contoso",
        "identity": "user-a",
        "team_id": "t1",
        "scope": "Demo\\Core|descendants=True",
        "period": "Demo\\Sprint 42",
        "engine_version": "0.1.0.dev0",
    }
    base.update(overrides)
    return CacheKey(**base)  # type: ignore[arg-type]


def test_cache_round_trip_within_ttl(tmp_path):
    cache = CollectionCache(tmp_path / "cache")
    cache.put(_key(), {"items": [101]}, now=AS_OF)
    assert cache.get(_key(), now=AS_OF + timedelta(minutes=5)) == {"items": [101]}


def test_cache_expires_after_ttl(tmp_path):
    cache = CollectionCache(tmp_path / "cache", ttl=timedelta(minutes=1))
    cache.put(_key(), {"items": [101]}, now=AS_OF)
    assert cache.get(_key(), now=AS_OF + timedelta(minutes=2)) is None


@pytest.mark.parametrize(
    "override",
    [
        {"identity": "user-b"},
        {"organization": "outra"},
        {"team_id": "t2"},
        {"scope": "Demo\\Outra"},
        {"period": "Demo\\Sprint 43"},
        {"engine_version": "0.2.0"},
    ],
)
def test_cache_is_isolated_by_every_key_dimension(tmp_path, override):
    cache = CollectionCache(tmp_path / "cache")
    cache.put(_key(), {"items": [101]}, now=AS_OF)
    assert cache.get(_key(**override), now=AS_OF) is None


def test_identity_is_stored_only_as_an_opaque_hash(tmp_path):
    cache = CollectionCache(tmp_path / "cache")
    path = cache.put(_key(), {"items": [101]}, now=AS_OF)
    assert "user-a" not in path.read_text(encoding="utf-8")
    assert "user-a" not in str(path)


def test_cache_clear_removes_entries(tmp_path):
    cache = CollectionCache(tmp_path / "cache")
    cache.put(_key(), {"items": []}, now=AS_OF)
    cache.clear()
    assert cache.get(_key(), now=AS_OF) is None


def test_hash_payload_is_stable_regardless_of_key_order():
    assert hash_payload({"a": 1, "b": 2}) == hash_payload({"b": 2, "a": 1})
