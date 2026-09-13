"""Composição do bloco histórico do relatório (T21).

Sem cobertura histórica demonstrada, o bloco fica indisponível com motivo: nenhum dia passado
é interpolado e nenhuma série é reconstruída a partir da última alteração genérica.
"""

from __future__ import annotations

from datetime import datetime

from ado_team_compass.contracts.config import TeamConfig
from ado_team_compass.contracts.facts import FactSet
from ado_team_compass.contracts.history import HistorySet
from ado_team_compass.contracts.report import HistoryBlock, SeriesPoint
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

__all__ = ["build_history_block"]


def build_history_block(
    history: HistorySet,
    facts: FactSet,
    team: TeamConfig,
    *,
    iteration_path: str | None,
    commitment_at: datetime,
    as_of: datetime,
    window_start: datetime | None = None,
) -> HistoryBlock:
    """Monta o bloco histórico da equipe para a janela analisada."""
    if not history.coverage.is_usable or iteration_path is None:
        return HistoryBlock(
            available=False,
            reasons=tuple(
                dict.fromkeys(
                    (
                        "histórico indisponível: cobertura insuficiente ou iteração não resolvida",
                        *history.coverage.reasons,
                    )
                )
            ),
        )

    reasons: list[str] = list(history.coverage.reasons)
    commitment_configured = team.history.commitment_at is not None
    baseline = build_baseline(
        history,
        iteration_path=iteration_path,
        at=commitment_at,
        commitment_configured=commitment_configured,
    )
    reasons.extend(baseline.reasons)

    ratio = say_do(baseline, history, at=as_of)
    if ratio.reason:
        reasons.append(ratio.reason)
    carry = carry_over(baseline, history, at=as_of)
    points = committed_points(baseline, history, at=as_of)
    reasons.extend(points.reasons)

    changes = scope_changes(
        history, iteration_path=iteration_path, since=commitment_at, until=as_of
    )
    reasons.extend(changes.reasons)

    since = window_start or commitment_at
    buckets, throughput_reasons = throughput_by_week(history, since=since, until=as_of)
    reasons.extend(throughput_reasons)

    cycle_samples, cycle_reasons = cycle_times(history, since=since, until=as_of)
    reasons.extend(cycle_reasons)
    created_at = {item.id: item.created_at for item in facts.items if item.created_at is not None}
    lead_samples, lead_reasons = lead_times(history, created_at, since=since, until=as_of)
    reasons.extend(lead_reasons)

    cycle_p50 = percentile(cycle_samples, 50)
    cycle_p85 = percentile(cycle_samples, 85)
    lead_p50 = percentile(lead_samples, 50)
    aging, aging_reasons = aging_wip(history, as_of=as_of)
    reasons.extend(aging_reasons)
    known_aging = [entry.days for entry in aging if entry.days is not None]

    return HistoryBlock(
        available=True,
        baseline_label=baseline.label,
        baseline_is_technical=baseline.is_technical,
        baseline_size=len(baseline.items),
        say_do=ratio.value,
        say_do_numerator=ratio.numerator,
        say_do_denominator=ratio.denominator,
        carry_over=carry.value,
        scope_entered=tuple(event.item_id for event in changes.entered),
        scope_exited=tuple(event.item_id for event in changes.exited),
        scope_round_trip=changes.round_trip_item_ids,
        committed_points=points.committed,
        current_points=points.current,
        points_changed_item_ids=points.changed_item_ids,
        throughput=tuple(
            SeriesPoint(period=week.isoformat(), value=value)
            for week, value in sorted(buckets.items())
        ),
        reopened_item_ids=reopened_completions(history, since=since, until=as_of),
        cycle_time_p50=cycle_p50.value,
        cycle_time_p85=cycle_p85.value,
        cycle_time_sample=cycle_p50.sample_size,
        lead_time_p50=lead_p50.value,
        lead_time_sample=lead_p50.sample_size,
        small_sample=cycle_p50.is_small_sample or lead_p50.is_small_sample,
        aging_unknown_item_ids=tuple(entry.item_id for entry in aging if entry.days is None),
        oldest_aging_days=max(known_aging) if known_aging else None,
        reasons=tuple(dict.fromkeys(reasons)),
    )


def small_sample_note(sample_size: int) -> str:
    return (
        f"amostra de {sample_size} itens abaixo da referência de {SMALL_SAMPLE_THRESHOLD}: "
        "percentis são indicativos, não previsão"
    )
