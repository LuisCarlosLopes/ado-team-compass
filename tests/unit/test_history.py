"""T17, T18 e T20 — histórico, compromisso e fluxo. Cenários V17, V18, V19 e V33."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from ado_team_compass.adapters.ado_mcp import AdoMcpClient
from ado_team_compass.collect.history import collect_history
from ado_team_compass.contracts.config import StateCategory
from ado_team_compass.contracts.history import HistoryCoverage, HistorySet, ItemRevision
from ado_team_compass.demo import demo_team
from ado_team_compass.demo.dataset import READ_TOOLS, default_responses, transport
from ado_team_compass.metrics.commitment import (
    build_baseline,
    carry_over,
    committed_points,
    say_do,
    scope_changes,
)
from ado_team_compass.metrics.flow import (
    SMALL_SAMPLE_THRESHOLD,
    aging_wip,
    cycle_times,
    lead_times,
    percentile,
    reopened_completions,
    throughput_by_week,
)

SPRINT = "Demo\\Sprint 42"
OUTRA = "Demo\\Sprint 43"
CUT = datetime(2026, 9, 14, 3, tzinfo=UTC)
END = datetime(2026, 9, 19, 3, tzinfo=UTC)


def _revision(
    item_id: int,
    day: int,
    *,
    state: str = "Committed",
    category: StateCategory | None = StateCategory.IN_PROGRESS,
    iteration: str | None = SPRINT,
    points: str | None = None,
    revision: int = 1,
    hour: int = 9,
) -> ItemRevision:
    return ItemRevision(
        item_id=item_id,
        revision=revision,
        changed_at=datetime(2026, 9, day, hour, tzinfo=UTC),
        state=state,
        state_category=category,
        iteration_path=iteration,
        story_points=Decimal(points) if points else None,
    )


def _history(*revisions: ItemRevision, usable: bool = True) -> HistorySet:
    item_ids = {revision.item_id for revision in revisions}
    return HistorySet(
        collected_at=END,
        revisions=revisions,
        coverage=HistoryCoverage(
            requested_items=len(item_ids),
            items_with_revisions=len(item_ids) if usable else 0,
            reasons=() if usable else ("sem revisões",),
        ),
    )


# -- T17: coleta ---------------------------------------------------------------------
def test_v33_history_is_unavailable_when_the_catalog_lacks_the_action():
    """A ferramenta de itens existe, mas o catálogo não anuncia a ação de revisões."""
    client = AdoMcpClient(
        transport=transport(
            default_responses(),
            tools=READ_TOOLS,
            actions_override={"wit_work_item": ("get", "get_batch", "list_for_iteration")},
        )
    )
    client.handshake()
    history = collect_history(client, demo_team(), [101, 102], collected_at=END)
    assert history.revisions == ()
    assert not history.coverage.is_usable
    assert any("indisponível no catálogo" in reason for reason in history.coverage.reasons)


def test_history_collection_normalizes_revisions_and_declares_limits():
    tools = READ_TOOLS
    responses = {
        **default_responses(),
        "wit_work_item:list_revisions": [
            {
                "value": [
                    {
                        "rev": 1,
                        "fields": {
                            "System.ChangedDate": "2026-09-14T12:00:00Z",
                            "System.State": "Committed",
                            "System.IterationPath": SPRINT,
                        },
                    },
                    {
                        "rev": 2,
                        "fields": {
                            "System.ChangedDate": "2026-09-16T12:00:00Z",
                            "System.State": "Done",
                            "System.IterationPath": SPRINT,
                        },
                    },
                ]
            }
        ],
    }
    client = AdoMcpClient(transport=transport(responses, tools=tools))
    client.handshake()
    history = collect_history(client, demo_team(), [101], collected_at=END)
    assert len(history.revisions) == 2
    assert history.revisions[1].state_category is StateCategory.COMPLETED
    assert history.coverage.is_usable
    assert any("itens excluídos" in reason for reason in history.coverage.reasons)


def test_history_without_revisions_for_one_item_is_not_usable():
    tools = READ_TOOLS
    responses = {
        **default_responses(),
        "wit_work_item:list_revisions": [{"value": []}, {"value": []}],
    }
    client = AdoMcpClient(transport=transport(responses, tools=tools))
    client.handshake()
    history = collect_history(client, demo_team(), [101, 102], collected_at=END)
    assert not history.coverage.is_usable


# -- T18: compromisso ----------------------------------------------------------------
def test_technical_baseline_is_labelled_when_there_is_no_configured_cut():
    history = _history(_revision(1, 13), _revision(2, 13))
    baseline = build_baseline(history, iteration_path=SPRINT, at=CUT, commitment_configured=False)
    assert baseline.is_technical
    assert baseline.label == "baseline técnica"
    assert any("não prova compromisso confirmado" in reason for reason in baseline.reasons)
    assert baseline.item_ids == (1, 2)


def test_configured_commitment_is_not_labelled_technical():
    history = _history(_revision(1, 13))
    baseline = build_baseline(history, iteration_path=SPRINT, at=CUT, commitment_configured=True)
    assert not baseline.is_technical and baseline.reasons == ()


def test_baseline_is_unavailable_without_history_coverage():
    history = _history(_revision(1, 13), usable=False)
    baseline = build_baseline(history, iteration_path=SPRINT, at=CUT, commitment_configured=True)
    assert not baseline.is_available
    assert any("cobertura histórica insuficiente" in reason for reason in baseline.reasons)


# V17 — corte histórico seguido de mudança de pontos e área.
def test_v17_baseline_freezes_points_and_later_changes_do_not_contaminate_it():
    history = _history(
        _revision(1, 13, points="5"),
        _revision(1, 16, points="13", revision=2),
        _revision(2, 13, points="3"),
    )
    baseline = build_baseline(history, iteration_path=SPRINT, at=CUT, commitment_configured=True)
    points = committed_points(baseline, history, at=END)
    assert points.committed == Decimal(8)
    assert points.current == Decimal(16)
    assert points.changed_item_ids == (1,)
    assert any("não medem produtividade" in reason for reason in points.reasons)


def test_item_created_after_the_cut_is_not_in_the_baseline():
    history = _history(_revision(1, 13), _revision(9, 16))
    baseline = build_baseline(history, iteration_path=SPRINT, at=CUT, commitment_configured=True)
    assert baseline.item_ids == (1,)


def test_say_do_counts_only_baseline_items():
    history = _history(
        _revision(1, 13),
        _revision(1, 17, state="Done", category=StateCategory.COMPLETED, revision=2),
        _revision(2, 13),
        # Item adicionado depois do corte e concluído: não entra no numerador.
        _revision(9, 16),
        _revision(9, 17, state="Done", category=StateCategory.COMPLETED, revision=2),
    )
    baseline = build_baseline(history, iteration_path=SPRINT, at=CUT, commitment_configured=True)
    ratio = say_do(baseline, history, at=END)
    assert (ratio.numerator, ratio.denominator) == (1, 2)
    assert ratio.value == Decimal("0.5")


# V19 — item entra e sai da sprint; baseline vazia.
def test_v19_entry_and_exit_are_both_visible():
    history = _history(
        _revision(5, 15, iteration=SPRINT),
        _revision(5, 17, iteration=OUTRA, revision=2),
    )
    changes = scope_changes(history, iteration_path=SPRINT, since=CUT, until=END)
    assert [event.item_id for event in changes.entered] == [5]
    assert [event.item_id for event in changes.exited] == [5]
    assert changes.round_trip_item_ids == (5,)


def test_v19_empty_baseline_makes_say_do_null():
    history = _history(_revision(5, 16))
    baseline = build_baseline(history, iteration_path=SPRINT, at=CUT, commitment_configured=True)
    ratio = say_do(baseline, history, at=END)
    assert ratio.value is None and ratio.reason is not None
    assert carry_over(baseline, history, at=END).value is None


def test_carry_over_keeps_removed_items_visible():
    history = _history(
        _revision(1, 13),
        _revision(1, 17, state="Removed", category=StateCategory.REMOVED, revision=2),
        _revision(2, 13),
        _revision(2, 17, state="Done", category=StateCategory.COMPLETED, revision=2),
    )
    baseline = build_baseline(history, iteration_path=SPRINT, at=CUT, commitment_configured=True)
    ratio = carry_over(baseline, history, at=END)
    assert (ratio.numerator, ratio.denominator) == (1, 2)


def test_scope_changes_are_unavailable_without_coverage():
    history = _history(_revision(1, 15), usable=False)
    changes = scope_changes(history, iteration_path=SPRINT, since=CUT, until=END)
    assert changes.entered == () and changes.exited == ()
    assert any("indisponível" in reason for reason in changes.reasons)


# -- T20: fluxo -----------------------------------------------------------------------
# V18 — item concluído, reaberto e concluído novamente.
def test_v18_reopened_item_counts_one_delivery_and_is_tracked_separately():
    history = _history(
        _revision(1, 14, hour=8),
        _revision(1, 15, state="Done", category=StateCategory.COMPLETED, revision=2),
        _revision(1, 16, state="Committed", revision=3),
        _revision(1, 17, state="Done", category=StateCategory.COMPLETED, revision=4),
    )
    buckets, reasons = throughput_by_week(history, since=CUT, until=END)
    assert sum(buckets.values()) == 1
    assert reasons == ()
    assert reopened_completions(history, since=CUT, until=END) == (1,)


def test_throughput_keeps_weeks_without_delivery_as_zero():
    history = _history(
        _revision(1, 14),
        _revision(1, 15, state="Done", category=StateCategory.COMPLETED, revision=2),
    )
    buckets, _ = throughput_by_week(history, since=datetime(2026, 8, 31, tzinfo=UTC), until=END)
    assert len(buckets) >= 3
    assert sorted(buckets.values()) == [0, 0, 1]


def test_cycle_time_uses_first_start_and_first_completion():
    history = _history(
        _revision(1, 14, hour=9),
        _revision(1, 16, state="Done", category=StateCategory.COMPLETED, revision=2, hour=9),
    )
    samples, reasons = cycle_times(history, since=CUT, until=END)
    assert [sample.days for sample in samples] == [Decimal("2.00")]
    assert reasons == ()


def test_cycle_time_skips_item_without_observed_start():
    history = _history(
        _revision(1, 14, state="New", category=StateCategory.PROPOSED),
        _revision(1, 16, state="Done", category=StateCategory.COMPLETED, revision=2),
    )
    samples, reasons = cycle_times(history, since=CUT, until=END)
    assert samples == ()
    assert any("sem entrada observada" in reason for reason in reasons)


def test_lead_time_requires_creation_date_and_is_named_honestly():
    history = _history(
        _revision(1, 14),
        _revision(1, 16, state="Done", category=StateCategory.COMPLETED, revision=2),
    )
    created = {1: datetime(2026, 9, 10, 9, tzinfo=UTC)}
    samples, reasons = lead_times(history, created, since=CUT, until=END)
    assert samples[0].days == Decimal("6.00")
    samples_without, reasons_without = lead_times(history, {}, since=CUT, until=END)
    assert samples_without == ()
    assert any("criação desconhecida" in reason for reason in reasons_without)
    assert reasons == ()


def test_aging_starts_at_the_reopening_for_a_reopened_item():
    history = _history(
        _revision(1, 14, hour=9),
        _revision(1, 15, state="Done", category=StateCategory.COMPLETED, revision=2),
        _revision(1, 17, state="Committed", revision=3, hour=9),
    )
    items, _ = aging_wip(history, as_of=datetime(2026, 9, 19, 9, tzinfo=UTC))
    assert items[0].days == Decimal("2.00")
    assert items[0].reopened


def test_aging_without_observed_start_is_unknown_not_guessed():
    history = _history(_revision(1, 14, state="New", category=StateCategory.PROPOSED))
    items, _ = aging_wip(history, as_of=END, only_started=False)
    assert items[0].days is None
    assert "última alteração genérica" in (items[0].reason or "")


def test_percentile_uses_nearest_rank_and_publishes_the_sample():
    samples, _ = cycle_times(
        _history(
            *[
                revision
                for index in range(1, 5)
                for revision in (
                    _revision(index, 14, hour=9),
                    _revision(
                        index,
                        14 + index,
                        state="Done",
                        category=StateCategory.COMPLETED,
                        revision=2,
                        hour=9,
                    ),
                )
            ]
        ),
        since=CUT,
        until=END,
    )
    result = percentile(samples, 85)
    assert result.method == "nearest-rank"
    assert result.unit == "dias corridos"
    assert result.sample_size == 4
    assert result.value == Decimal("4.00")
    assert result.is_small_sample
    assert f"{SMALL_SAMPLE_THRESHOLD}" in (result.reason or "")


def test_percentile_without_sample_is_null_with_reason():
    result = percentile((), 50, reasons=("sem conclusões no período",))
    assert result.value is None and result.sample_size == 0
    assert "sem conclusões" in (result.reason or "")


@pytest.mark.parametrize(
    "function",
    [
        lambda history: throughput_by_week(history, since=CUT, until=END)[1],
        lambda history: cycle_times(history, since=CUT, until=END)[1],
        lambda history: lead_times(history, {}, since=CUT, until=END)[1],
        lambda history: aging_wip(history, as_of=END)[1],
    ],
)
def test_flow_metrics_are_unavailable_without_coverage(function):
    history = _history(_revision(1, 14), usable=False)
    reasons = function(history)
    assert any("cobertura histórica insuficiente" in reason for reason in reasons)


def test_history_window_boundaries_are_respected():
    history = _history(
        _revision(1, 14),
        _revision(1, 20, state="Done", category=StateCategory.COMPLETED, revision=2),
    )
    samples, _ = cycle_times(history, since=CUT, until=END)
    assert samples == ()
    later, _ = cycle_times(history, since=CUT, until=END + timedelta(days=5))
    assert len(later) == 1
