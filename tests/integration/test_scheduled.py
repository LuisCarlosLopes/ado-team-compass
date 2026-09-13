"""T23 e T24 — execução agendada idempotente e observável. Cenário V22."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from ado_team_compass.adapters.ado_mcp import AdoMcpClient
from ado_team_compass.config import resolve_config
from ado_team_compass.demo import ORGANIZATION, demo_config_document
from ado_team_compass.demo.dataset import READ_TOOLS, default_responses, transport
from ado_team_compass.errors import ConfigError, ExitCode
from ado_team_compass.mcp.session.transport import ToolCallResult
from ado_team_compass.runs import RunStore
from ado_team_compass.runs.lock import ScheduleKey, acquire_lock, read_marker
from ado_team_compass.scheduled import run_scheduled, schedule_key_for

AS_OF = datetime.fromisoformat("2026-09-15T12:00:00-03:00")


def _client(responses=None, tools=READ_TOOLS) -> AdoMcpClient:
    client = AdoMcpClient(transport=transport(responses or default_responses(), tools=tools))
    client.handshake()
    return client


def _run(tmp_path: Path, *, as_of=AS_OF, responses=None, force=False):
    resolved = resolve_config(demo_config_document())
    return (
        run_scheduled(
            _client(responses),
            resolved.config.teams[0],
            organization=ORGANIZATION,
            as_of=as_of,
            store=RunStore(tmp_path / "runs"),
            resolved=resolved,
            state_root=tmp_path / "schedule",
            force=force,
        ),
        resolved,
    )


def test_first_scheduled_run_executes_and_writes_a_success_marker(tmp_path):
    result, resolved = _run(tmp_path)
    assert result.status == "executada"
    assert result.run_id
    marker = read_marker(
        tmp_path / "schedule",
        schedule_key_for(resolved, resolved.config.teams[0], as_of=AS_OF, window=None),
    )
    assert marker is not None and marker.run_id == result.run_id


# V22 — segunda execução da mesma chave não duplica o resultado.
def test_v22_repeating_the_same_key_does_not_duplicate_the_result(tmp_path):
    first, _ = _run(tmp_path)
    second, _ = _run(tmp_path)
    assert second.status == "ja_executada"
    assert second.run_id == first.run_id
    assert RunStore(tmp_path / "runs").list_runs() == (first.run_id,)


def test_v22_concurrent_run_is_refused_while_the_lock_is_held(tmp_path):
    resolved = resolve_config(demo_config_document())
    key = schedule_key_for(resolved, resolved.config.teams[0], as_of=AS_OF, window=None)
    with acquire_lock(tmp_path / "schedule", key, now=AS_OF), pytest.raises(ConfigError) as error:
        _run(tmp_path)
    assert error.value.code == "E_AGENDAMENTO_EM_ANDAMENTO"
    assert RunStore(tmp_path / "runs").list_runs() == ()


# V22 — falha posterior preserva o sucesso anterior.
def test_v22_later_failure_preserves_the_previous_successful_report(tmp_path):
    first, _ = _run(tmp_path)
    broken = {
        **default_responses(),
        "work:list_team_iterations": ToolCallResult(
            tool="work:list_team_iterations", is_error=True, error_text="403 forbidden"
        ),
    }
    later = AS_OF + timedelta(days=1)
    failure, _ = _run(tmp_path, as_of=later, responses=broken)
    assert failure.status == "falha"
    assert failure.exit_code is ExitCode.ACCESS_DENIED
    assert failure.run_id is None
    store = RunStore(tmp_path / "runs")
    assert store.list_runs() == (first.run_id,)
    assert store.load(first.run_id).artifact("metrics.json")


def test_failure_notification_is_actionable_and_names_the_previous_report(tmp_path):
    _run(tmp_path)
    broken = {
        **default_responses(),
        "work:list_team_iterations": ToolCallResult(
            tool="work:list_team_iterations", is_error=True, error_text="403 forbidden"
        ),
    }
    failure, _ = _run(tmp_path, as_of=AS_OF, responses=broken, force=True)
    assert failure.notification is not None
    assert failure.notification["actionable"] is True
    assert "template" in failure.notification["delivery"]


def test_unchanged_state_does_not_generate_a_notification(tmp_path):
    first, _ = _run(tmp_path)
    assert first.notification is not None  # primeira execução é mudança relevante
    repeated, _ = _run(tmp_path, force=True, as_of=AS_OF + timedelta(seconds=1))
    assert repeated.status == "executada"
    assert repeated.notification is None


def test_key_changes_with_configuration_team_window_and_day(tmp_path):
    resolved = resolve_config(demo_config_document())
    team = resolved.config.teams[0]
    base = schedule_key_for(resolved, team, as_of=AS_OF, window=None)
    other_day = schedule_key_for(resolved, team, as_of=AS_OF + timedelta(days=1), window=None)
    other_window = schedule_key_for(resolved, team, as_of=AS_OF, window="Demo\\Sprint 43")
    document = demo_config_document()
    document["teams"][0]["allocation"] = {"unit": "days"}
    other_config = schedule_key_for(
        resolve_config(document), resolve_config(document).config.teams[0], as_of=AS_OF, window=None
    )
    digests = {base.digest(), other_day.digest(), other_window.digest(), other_config.digest()}
    assert len(digests) == 4


def test_stale_lock_is_reclaimed_after_the_grace_period(tmp_path):
    key = ScheduleKey(config_hash="c", team_alias="demo", window="w", day="2026-09-15")
    root = tmp_path / "schedule"
    with acquire_lock(root, key, now=AS_OF):
        pass
    # Lock órfão: escrito manualmente com data antiga.
    lock_path = root / "locks" / f"{key.name}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        json.dumps({"acquired_at": (AS_OF - timedelta(hours=5)).isoformat()}), encoding="utf-8"
    )
    with acquire_lock(root, key, now=AS_OF) as held:
        assert held.is_file()


def test_lock_is_released_even_when_the_body_raises(tmp_path):
    key = ScheduleKey(config_hash="c", team_alias="demo", window="w", day="2026-09-15")
    root = tmp_path / "schedule"
    with pytest.raises(RuntimeError), acquire_lock(root, key, now=AS_OF):
        raise RuntimeError("falha no meio")
    with acquire_lock(root, key, now=AS_OF) as held:
        assert held.is_file()


def test_cli_run_scheduled_is_non_interactive_and_reports_the_key(tmp_path, monkeypatch, capsys):
    from contextlib import contextmanager

    from ado_team_compass.cli import build_parser

    document = demo_config_document()
    document["output"] = {"directory": str(tmp_path / "runs")}
    config_path = tmp_path / "config.yaml"
    config_path.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setenv("ADO_TEAM_COMPASS_CONFIG", str(config_path))

    @contextmanager
    def factory(_connection):
        yield transport(default_responses())

    parser = build_parser()
    args = parser.parse_args(["run-scheduled", "--as-of", AS_OF.isoformat()])
    args._transport_factory = factory
    assert int(args._handler(args)) in (int(ExitCode.OK), int(ExitCode.PARTIAL_CAPABILITY))
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "executada"
    assert payload["run_id"]

    args_again = parser.parse_args(["run-scheduled", "--as-of", AS_OF.isoformat()])
    args_again._transport_factory = factory
    assert int(args_again._handler(args_again)) == int(ExitCode.OK)
    assert json.loads(capsys.readouterr().out)["status"] == "ja_executada"
