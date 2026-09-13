"""Compromisso, mudança de escopo e carry-over a partir de revisões (plano 4.1.5, T18).

Regras preservadas:

- sem corte configurado, o início local da sprint é baseline **técnica**, rotulada como tal,
  sem alegar compromisso confirmado;
- say/do usa apenas itens da baseline; itens adicionados nunca entram no numerador;
- entradas e saídas de escopo são eventos separados, e o item que entra e sai dentro da
  sprint aparece nos dois lados, nunca apenas como saldo líquido;
- pontos comprometidos ficam congelados no corte; estimativas alteradas aparecem à parte;
- sem cobertura histórica suficiente, tudo isso fica indisponível com motivo.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from ado_team_compass.contracts.config import StateCategory
from ado_team_compass.contracts.history import HistorySet, ItemRevision

__all__ = [
    "Baseline",
    "BaselineItem",
    "ScopeChanges",
    "ScopeEvent",
    "build_baseline",
    "carry_over",
    "committed_points",
    "revision_at",
    "say_do",
    "scope_changes",
]

_CLOSED = (StateCategory.COMPLETED, StateCategory.REMOVED)


def revision_at(revisions: Sequence[ItemRevision], moment: datetime) -> ItemRevision | None:
    """Última revisão até o instante; nada antes do corte significa item inexistente então."""
    candidates = [revision for revision in revisions if revision.changed_at <= moment]
    if not candidates:
        return None
    return max(candidates, key=lambda revision: (revision.changed_at, revision.revision))


@dataclass(frozen=True)
class BaselineItem:
    """Item congelado no corte, com o que era verdade naquele instante."""

    item_id: int
    story_points: Decimal | None
    state_category: StateCategory | None
    iteration_path: str | None


@dataclass(frozen=True)
class Baseline:
    """Conjunto de itens elegíveis abertos no corte."""

    at: datetime
    iteration_path: str
    items: tuple[BaselineItem, ...]
    is_technical: bool
    label: str
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def item_ids(self) -> tuple[int, ...]:
        return tuple(item.item_id for item in self.items)

    @property
    def is_available(self) -> bool:
        return bool(self.items)


def build_baseline(
    history: HistorySet,
    *,
    iteration_path: str,
    at: datetime,
    commitment_configured: bool,
    eligible_types: Mapping[int, str] | None = None,
    requirement_types: Sequence[str] = (),
) -> Baseline:
    """Congela os itens elegíveis abertos na iteração no instante do corte."""
    reasons: list[str] = []
    if not history.coverage.is_usable:
        reasons.append(
            "cobertura histórica insuficiente: baseline e percentuais ficam indisponíveis"
        )
        return Baseline(
            at=at,
            iteration_path=iteration_path,
            items=(),
            is_technical=not commitment_configured,
            label="indisponível",
            reasons=tuple((*reasons, *history.coverage.reasons)),
        )

    items: list[BaselineItem] = []
    for item_id in history.item_ids():
        if requirement_types and eligible_types is not None:
            item_type = eligible_types.get(item_id)
            if item_type is None or item_type not in requirement_types:
                continue
        revision = revision_at(history.for_item(item_id), at)
        if revision is None:
            continue
        if revision.iteration_path != iteration_path:
            continue
        if revision.state_category in _CLOSED:
            continue
        items.append(
            BaselineItem(
                item_id=item_id,
                story_points=revision.story_points,
                state_category=revision.state_category,
                iteration_path=revision.iteration_path,
            )
        )

    if not commitment_configured:
        reasons.append(
            "sem corte de compromisso configurado: o início local da sprint é baseline "
            "técnica e não prova compromisso confirmado"
        )
    return Baseline(
        at=at,
        iteration_path=iteration_path,
        items=tuple(sorted(items, key=lambda item: item.item_id)),
        is_technical=not commitment_configured,
        label="baseline técnica" if not commitment_configured else "compromisso configurado",
        reasons=tuple(reasons),
    )


@dataclass(frozen=True)
class ScopeEvent:
    """Entrada ou saída de um item no escopo da iteração, com o instante observado."""

    item_id: int
    at: datetime
    direction: str  # "entrada" ou "saida"
    reason: str | None = None


@dataclass(frozen=True)
class ScopeChanges:
    """Entradas e saídas separadas; o saldo líquido nunca aparece sozinho."""

    entered: tuple[ScopeEvent, ...]
    exited: tuple[ScopeEvent, ...]
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def round_trip_item_ids(self) -> tuple[int, ...]:
        """Itens que entraram e saíram dentro da mesma janela."""
        entered = {event.item_id for event in self.entered}
        exited = {event.item_id for event in self.exited}
        return tuple(sorted(entered & exited))


def scope_changes(
    history: HistorySet,
    *,
    iteration_path: str,
    since: datetime,
    until: datetime,
) -> ScopeChanges:
    """Detecta entradas e saídas do escopo desde o corte, preservando ida e volta."""
    if not history.coverage.is_usable:
        return ScopeChanges(
            entered=(),
            exited=(),
            reasons=(
                "mudança de escopo indisponível: cobertura histórica insuficiente",
                *history.coverage.reasons,
            ),
        )

    entered: list[ScopeEvent] = []
    exited: list[ScopeEvent] = []
    for item_id in history.item_ids():
        revisions = history.for_item(item_id)
        baseline_revision = revision_at(revisions, since)
        inside = (
            baseline_revision is not None and baseline_revision.iteration_path == iteration_path
        )
        for revision in revisions:
            if not since < revision.changed_at <= until:
                continue
            now_inside = revision.iteration_path == iteration_path
            if now_inside and not inside:
                entered.append(
                    ScopeEvent(item_id=item_id, at=revision.changed_at, direction="entrada")
                )
            elif inside and not now_inside:
                exited.append(
                    ScopeEvent(
                        item_id=item_id,
                        at=revision.changed_at,
                        direction="saida",
                        reason=f"iteração passou a {revision.iteration_path!r}",
                    )
                )
            inside = now_inside
    return ScopeChanges(entered=tuple(entered), exited=tuple(exited))


@dataclass(frozen=True)
class Ratio:
    """Razão com numerador, denominador e motivo quando não há percentual."""

    numerator: int
    denominator: int
    value: Decimal | None
    reason: str | None = None


def say_do(baseline: Baseline, history: HistorySet, *, at: datetime) -> Ratio:
    """Itens da baseline concluídos no corte final sobre os itens da baseline."""
    if not baseline.is_available:
        return Ratio(0, 0, None, "sem baseline utilizável, say/do é nulo")
    completed = 0
    for item in baseline.items:
        revision = revision_at(history.for_item(item.item_id), at)
        if revision is not None and revision.state_category is StateCategory.COMPLETED:
            completed += 1
    denominator = len(baseline.items)
    if denominator == 0:
        return Ratio(completed, 0, None, "denominador zero: say/do é nulo")
    return Ratio(completed, denominator, Decimal(completed) / Decimal(denominator))


def carry_over(baseline: Baseline, history: HistorySet, *, at: datetime) -> Ratio:
    """Itens da baseline não concluídos ao final, sobre a baseline.

    Itens removidos continuam visíveis no numerador com motivo; isto não é o mesmo que itens
    efetivamente movidos para a próxima sprint.
    """
    if not baseline.is_available:
        return Ratio(0, 0, None, "sem baseline utilizável, carry-over é nulo")
    pending = 0
    for item in baseline.items:
        revision = revision_at(history.for_item(item.item_id), at)
        if revision is None or revision.state_category is not StateCategory.COMPLETED:
            pending += 1
    denominator = len(baseline.items)
    return Ratio(
        pending,
        denominator,
        Decimal(pending) / Decimal(denominator) if denominator else None,
        None if denominator else "denominador zero: carry-over é nulo",
    )


@dataclass(frozen=True)
class CommittedPoints:
    """Pontos congelados no corte e o que mudou depois, sem misturar os dois."""

    committed: Decimal | None
    current: Decimal | None
    changed_item_ids: tuple[int, ...]
    items_without_points: int
    reasons: tuple[str, ...] = field(default_factory=tuple)


def committed_points(baseline: Baseline, history: HistorySet, *, at: datetime) -> CommittedPoints:
    """Soma os pontos congelados e destaca as estimativas alteradas depois do corte."""
    if not baseline.is_available:
        return CommittedPoints(
            committed=None,
            current=None,
            changed_item_ids=(),
            items_without_points=0,
            reasons=("sem baseline utilizável, pontos comprometidos ficam indisponíveis",),
        )
    committed = Decimal(0)
    current = Decimal(0)
    known = 0
    missing = 0
    changed: list[int] = []
    for item in baseline.items:
        latest = revision_at(history.for_item(item.item_id), at)
        if item.story_points is None:
            missing += 1
        else:
            committed += item.story_points
            known += 1
        if latest is not None and latest.story_points is not None:
            current += latest.story_points
        if (
            latest is not None
            and item.story_points is not None
            and latest.story_points is not None
            and latest.story_points != item.story_points
        ):
            changed.append(item.item_id)
    reasons: list[str] = []
    if missing:
        reasons.append(f"{missing} itens da baseline não tinham pontos no corte")
    reasons.append("pontos não são comparáveis entre equipes e não medem produtividade")
    return CommittedPoints(
        committed=committed if known else None,
        current=current if known else None,
        changed_item_ids=tuple(sorted(changed)),
        items_without_points=missing,
        reasons=tuple(reasons),
    )
