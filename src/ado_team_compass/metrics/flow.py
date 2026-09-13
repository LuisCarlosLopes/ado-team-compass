"""Métricas de fluxo a partir de revisões (plano 4.1.5, T20).

Definições implementadas, todas dependentes de cobertura histórica demonstrada:

- throughput: itens únicos na **primeira** transição para concluído por período; conclusão
  posterior de item reaberto é registrada à parte e não duplica entrega nova;
- cycle time: da primeira entrada em iniciado à primeira conclusão, coorte por primeira
  conclusão no período;
- lead time: da criação à primeira conclusão, na mesma coorte; não é tempo até valor em
  produção;
- aging WIP: agora menos o início do episódio aberto atual; se reaberto, o episódio começa na
  reabertura; sem histórico, o início não é estimado pela última alteração genérica;
- percentis: método nearest-rank, em dias corridos, com tamanho de amostra publicado.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from ado_team_compass.contracts.config import StateCategory
from ado_team_compass.contracts.history import HistorySet, ItemRevision

__all__ = [
    "SMALL_SAMPLE_THRESHOLD",
    "AgingItem",
    "FlowSample",
    "Percentile",
    "aging_wip",
    "cycle_times",
    "lead_times",
    "percentile",
    "reopened_completions",
    "throughput_by_week",
]

#: Abaixo deste tamanho, a amostra é publicada como pequena (plano 4.1.5).
SMALL_SAMPLE_THRESHOLD = 20

_STARTED = StateCategory.IN_PROGRESS
_DONE = StateCategory.COMPLETED


@dataclass(frozen=True)
class FlowSample:
    """Uma observação de tempo, em dias corridos, com o item de origem."""

    item_id: int
    days: Decimal
    completed_at: datetime


@dataclass(frozen=True)
class Percentile:
    """Percentil nearest-rank com amostra e aviso de amostra pequena."""

    percentile: int
    value: Decimal | None
    sample_size: int
    method: str = "nearest-rank"
    unit: str = "dias corridos"
    reason: str | None = None

    @property
    def is_small_sample(self) -> bool:
        return 0 < self.sample_size < SMALL_SAMPLE_THRESHOLD


def _first_transition(
    revisions: Sequence[ItemRevision], category: StateCategory
) -> ItemRevision | None:
    for revision in revisions:
        if revision.state_category is category:
            return revision
    return None


def _completions(revisions: Sequence[ItemRevision]) -> list[ItemRevision]:
    """Transições para concluído, ignorando revisões que apenas repetem o estado."""
    completions: list[ItemRevision] = []
    previous: StateCategory | None = None
    for revision in revisions:
        if revision.state_category is _DONE and previous is not _DONE:
            completions.append(revision)
        previous = revision.state_category
    return completions


def throughput_by_week(
    history: HistorySet, *, since: datetime, until: datetime
) -> tuple[dict[date, int], tuple[str, ...]]:
    """Contagem de primeiras conclusões por semana ISO; semanas sem entrega ficam com zero."""
    if not history.coverage.is_usable:
        return {}, (
            "throughput indisponível: cobertura histórica insuficiente",
            *history.coverage.reasons,
        )
    buckets: dict[date, int] = {}
    cursor = _week_start(since.date())
    last = _week_start(until.date())
    while cursor <= last:
        buckets[cursor] = 0
        cursor += timedelta(days=7)

    for item_id in history.item_ids():
        completions = _completions(history.for_item(item_id))
        if not completions:
            continue
        first = completions[0]
        if not since <= first.changed_at <= until:
            continue
        week = _week_start(first.changed_at.date())
        if week in buckets:
            buckets[week] += 1
    return buckets, ()


def reopened_completions(
    history: HistorySet, *, since: datetime, until: datetime
) -> tuple[int, ...]:
    """Itens que voltaram a ser concluídos depois de reabertos, contados à parte."""
    repeated: list[int] = []
    for item_id in history.item_ids():
        completions = _completions(history.for_item(item_id))
        later = [
            completion for completion in completions[1:] if since <= completion.changed_at <= until
        ]
        if later:
            repeated.append(item_id)
    return tuple(sorted(repeated))


def cycle_times(
    history: HistorySet, *, since: datetime, until: datetime
) -> tuple[tuple[FlowSample, ...], tuple[str, ...]]:
    """Coorte por primeira conclusão no período; item sem início observado fica de fora."""
    if not history.coverage.is_usable:
        return (), (
            "cycle time indisponível: cobertura histórica insuficiente",
            *history.coverage.reasons,
        )
    samples: list[FlowSample] = []
    reasons: list[str] = []
    for item_id in history.item_ids():
        revisions = history.for_item(item_id)
        completions = _completions(revisions)
        if not completions:
            continue
        first_completion = completions[0]
        if not since <= first_completion.changed_at <= until:
            continue
        start = _first_transition(revisions, _STARTED)
        if start is None or start.changed_at > first_completion.changed_at:
            reasons.append(f"item {item_id}: sem entrada observada em iniciado antes da conclusão")
            continue
        samples.append(
            FlowSample(
                item_id=item_id,
                days=_days(first_completion.changed_at - start.changed_at),
                completed_at=first_completion.changed_at,
            )
        )
    return tuple(samples), tuple(reasons)


def lead_times(
    history: HistorySet,
    created_at: Mapping[int, datetime],
    *,
    since: datetime,
    until: datetime,
) -> tuple[tuple[FlowSample, ...], tuple[str, ...]]:
    """Criação até a primeira conclusão. O nome não promete tempo até valor em produção."""
    if not history.coverage.is_usable:
        return (), (
            "lead time indisponível: cobertura histórica insuficiente",
            *history.coverage.reasons,
        )
    samples: list[FlowSample] = []
    reasons: list[str] = []
    for item_id in history.item_ids():
        completions = _completions(history.for_item(item_id))
        if not completions:
            continue
        first_completion = completions[0]
        if not since <= first_completion.changed_at <= until:
            continue
        created = created_at.get(item_id)
        if created is None:
            reasons.append(f"item {item_id}: data de criação desconhecida")
            continue
        samples.append(
            FlowSample(
                item_id=item_id,
                days=_days(first_completion.changed_at - created),
                completed_at=first_completion.changed_at,
            )
        )
    return tuple(samples), tuple(reasons)


@dataclass(frozen=True)
class AgingItem:
    """Idade do episódio aberto atual de um item."""

    item_id: int
    days: Decimal | None
    episode_started_at: datetime | None
    reopened: bool = False
    reason: str | None = None


def aging_wip(
    history: HistorySet, *, as_of: datetime, only_started: bool = True
) -> tuple[tuple[AgingItem, ...], tuple[str, ...]]:
    """Idade do episódio aberto; item reaberto reinicia a contagem na reabertura."""
    if not history.coverage.is_usable:
        return (), (
            "aging indisponível: cobertura histórica insuficiente",
            *history.coverage.reasons,
        )
    results: list[AgingItem] = []
    for item_id in history.item_ids():
        revisions = history.for_item(item_id)
        current = revisions[-1] if revisions else None
        if current is None or current.state_category in (_DONE, StateCategory.REMOVED):
            continue
        if only_started and current.state_category is not _STARTED:
            continue
        episode_start = _episode_start(revisions)
        if episode_start is None:
            results.append(
                AgingItem(
                    item_id=item_id,
                    days=None,
                    episode_started_at=None,
                    reason=(
                        "início do episódio desconhecido: a última alteração genérica não "
                        "define quando o trabalho começou"
                    ),
                )
            )
            continue
        reopened = _was_reopened(revisions)
        results.append(
            AgingItem(
                item_id=item_id,
                days=_days(as_of - episode_start),
                episode_started_at=episode_start,
                reopened=reopened,
            )
        )
    return tuple(results), ()


def _episode_start(revisions: Sequence[ItemRevision]) -> datetime | None:
    """Início do episódio aberto atual: a reabertura mais recente ou a primeira entrada."""
    start: datetime | None = None
    for revision in revisions:
        if revision.state_category is _DONE:
            start = None
            continue
        if revision.state_category is _STARTED and start is None:
            start = revision.changed_at
    return start


def _was_reopened(revisions: Sequence[ItemRevision]) -> bool:
    return bool(_completions(revisions))


def percentile(
    samples: Sequence[FlowSample], target: int, *, reasons: Sequence[str] = ()
) -> Percentile:
    """Percentil nearest-rank; sem amostra, valor nulo com motivo."""
    if not samples:
        return Percentile(
            percentile=target,
            value=None,
            sample_size=0,
            reason="; ".join(reasons) or "amostra vazia: percentil é nulo",
        )
    ordered = sorted(sample.days for sample in samples)
    size = len(ordered)
    rank = max(1, -(-target * size // 100))  # teto de (target/100 * n)
    value = ordered[min(rank, size) - 1]
    reason = None
    if size < SMALL_SAMPLE_THRESHOLD:
        reason = f"amostra pequena: {size} itens (referência: {SMALL_SAMPLE_THRESHOLD})"
    return Percentile(percentile=target, value=value, sample_size=size, reason=reason)


@dataclass(frozen=True)
class Series:
    """Série descritiva por janela comparável; não conclui melhora ou piora sozinha."""

    buckets: dict[date, int] = field(default_factory=dict)
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def note(self) -> str:
        return (
            "série descritiva: variação entre janelas não demonstra melhora ou piora sem "
            "contexto e cobertura"
        )


def _days(delta: timedelta) -> Decimal:
    total = Decimal(delta.total_seconds()) / Decimal(86400)
    return total.quantize(Decimal("0.01"))


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())
