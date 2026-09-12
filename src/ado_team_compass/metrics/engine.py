"""Composição das métricas da situação atual a partir de fatos congelados.

Função pura: recebe fatos, configuração e o instante de referência; não acessa rede, relógio
do sistema nem LLM. Todo número produzido aponta para a métrica e a evidência de origem.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal

from ado_team_compass.contracts.common import (
    Capability,
    MetricStatus,
    QualityCounters,
    Quantity,
    Window,
)
from ado_team_compass.contracts.config import TeamConfig
from ado_team_compass.contracts.facts import FactSet, WorkItemFact
from ado_team_compass.contracts.metrics import Finding, Metric
from ado_team_compass.contracts.report import PersonRow, TeamReport
from ado_team_compass.metrics.allocation import (
    CLOSED_CATEGORIES,
    KnownLoad,
    accountable_items,
    classify_load,
    known_load,
)
from ado_team_compass.metrics.calendar import eligible_day_factors, reserved_capacity
from ado_team_compass.metrics.quality import assess_metric

__all__ = ["build_team_report"]

_ITEMS = "items"


def build_team_report(
    facts: FactSet,
    team: TeamConfig,
    *,
    run_id: str,
    as_of: datetime,
    window: Window | None,
    iteration_path: str | None = None,
    evidence_references: Mapping[str, str] | None = None,
    limitations: Sequence[str] = (),
) -> TeamReport:
    """Calcula métricas de equipe e por pessoa, com status e cobertura por métrica."""
    unit = team.allocation.unit
    notes = list(limitations)
    notes.extend(facts.reasons)

    accountable = accountable_items(
        facts.items, facts.relations, accounting_level=team.process.accounting_level
    )
    open_items = tuple(
        item
        for item in accountable
        if item.state_category is not None and item.state_category not in CLOSED_CATEGORIES
    )
    load = known_load(
        list(facts.items),
        unit=unit,
        relations=facts.relations,
        accounting_level=team.process.accounting_level,
    )

    day_factors = _day_factors(facts, team, as_of=as_of, window=window, notes=notes)
    capacity, capacity_counters = _team_capacity(facts, team, day_factors, notes=notes)
    has_reservations = bool(facts.reservations)

    metrics: list[Metric] = [
        assess_metric(
            "open_items_count",
            team,
            counters=QualityCounters(eligible=len(accountable), known=len(accountable)),
            quantity=Quantity(value=Decimal(len(open_items)), unit=_ITEMS),
        ),
        _blocked_metric(team, accountable),
        assess_metric(
            "known_remaining_work",
            team,
            counters=load.counters,
            quantity=load.quantity,
            has_reservations=has_reservations,
        ),
        assess_metric(
            "reserved_remaining_capacity",
            team,
            counters=capacity_counters,
            quantity=capacity,
            has_reservations=has_reservations,
        ),
    ]

    classification = classify_load(load, capacity, thresholds=team.allocation.thresholds)
    utilization_status, utilization_reason = _utilization_status(
        team, load, capacity, classification.ratio
    )
    utilization = assess_metric(
        "observed_utilization",
        team,
        counters=load.counters,
        has_reservations=has_reservations,
    )
    if utilization.status is not MetricStatus.NOT_APPLICABLE:
        utilization = utilization.model_copy(
            update={
                "status": utilization_status,
                "ratio": classification.ratio,
                "quantity": None,
                "window": window,
                "unavailable_reason": utilization_reason,
            }
        )
    metrics.append(utilization)
    if classification.reason:
        notes.append(f"classe {classification.load_class.value}: {classification.reason}")

    people = _person_rows(facts, team, day_factors, unit=unit, notes=notes)
    findings: list[Finding] = list(load.findings)

    return TeamReport(
        run_id=run_id,
        team_alias=team.alias,
        team_id=team.team_id,
        project_id=team.project_id,
        profile=team.profile.value,
        as_of=as_of.isoformat(),
        window=window,
        iteration_path=iteration_path,
        unit=unit,
        metrics=tuple(metrics),
        people=tuple(people),
        findings=tuple(findings),
        limitations=tuple(dict.fromkeys(notes)),
        partial_sources=facts.partial_sources,
        evidence_references=dict(evidence_references or {}),
    )


def _blocked_metric(team: TeamConfig, items: Sequence[WorkItemFact]) -> Metric:
    known = [item for item in items if item.blocked is not None]
    blocked = [item for item in known if item.blocked]
    return assess_metric(
        "blocked_items_count",
        team,
        counters=QualityCounters(
            eligible=len(items),
            known=len(known),
            missing=len(items) - len(known),
            reasons=("itens sem informação de impedimento",) if len(known) < len(items) else (),
        ),
        quantity=Quantity(value=Decimal(len(blocked)), unit=_ITEMS),
    )


def _day_factors(
    facts: FactSet,
    team: TeamConfig,
    *,
    as_of: datetime,
    window: Window | None,
    notes: list[str],
) -> dict[str, dict[date, Decimal]]:
    """Dias elegíveis por pessoa, aplicando folgas de equipe e pessoais como união."""
    if window is None:
        notes.append("sem janela resolvida, a capacidade restante não é calculável")
        return {}
    team_days_off = [entry for entry in facts.days_off if entry.person_id is None]
    factors: dict[str, dict[date, Decimal]] = {}
    for person in facts.people:
        personal = [entry for entry in facts.days_off if entry.person_id == person.id]
        factors[person.id] = eligible_day_factors(
            window, as_of, team.calendar, days_off=[*team_days_off, *personal]
        )
    return factors


def _team_capacity(
    facts: FactSet,
    team: TeamConfig,
    day_factors: Mapping[str, Mapping[date, Decimal]],
    *,
    notes: list[str],
) -> tuple[Quantity | None, QualityCounters]:
    """Capacidade restante reservada da equipe, somando pessoas na mesma unidade."""
    unit = team.allocation.unit
    people = sorted({reservation.person_id for reservation in facts.reservations})
    if not people:
        notes.append("nenhuma reserva de capacidade conhecida para a janela")
        return None, QualityCounters(eligible=0, known=0)

    total = Quantity(value=None, unit=unit)
    known = 0
    missing = 0
    reasons: list[str] = []
    for person_id in people:
        reservations = [
            reservation
            for reservation in facts.reservations
            if reservation.person_id == person_id and reservation.per_day.unit == unit
        ]
        if not reservations:
            missing += 1
            reasons.append(f"pessoa {person_id}: reserva em unidade incompatível com {unit!r}")
            continue
        person_capacity = reserved_capacity(reservations, day_factors.get(person_id, {}))
        if person_capacity.value is None:
            missing += 1
            reasons.append(f"pessoa {person_id}: capacidade diária desconhecida")
            continue
        known += 1
        total = total.add(person_capacity)
    notes.extend(reasons)
    return total, QualityCounters(
        eligible=len(people), known=known, missing=missing, reasons=tuple(reasons)
    )


def _utilization_status(
    team: TeamConfig,
    load: KnownLoad,
    capacity: Quantity | None,
    ratio: Decimal | None,
) -> tuple[MetricStatus, str | None]:
    if Capability.ALLOCATION not in team.capabilities:
        return MetricStatus.NOT_APPLICABLE, "capacidade allocation não habilitada"
    if capacity is None or capacity.value is None:
        return MetricStatus.UNAVAILABLE, "capacidade restante reservada desconhecida"
    if ratio is None:
        return (
            MetricStatus.UNAVAILABLE,
            "não há percentual comparável para a carga e a capacidade desta janela",
        )
    if not load.is_complete:
        return MetricStatus.PARTIAL, None
    return MetricStatus.AVAILABLE, None


def _person_rows(
    facts: FactSet,
    team: TeamConfig,
    day_factors: Mapping[str, Mapping[date, Decimal]],
    *,
    unit: str,
    notes: list[str],
) -> list[PersonRow]:
    """Uma linha por pessoa conhecida; carga sem responsável aparece em linha própria."""
    rows: list[PersonRow] = []
    names = {person.id: person.display_name for person in facts.people}
    people = sorted(names) or sorted({item.assigned_to for item in facts.items if item.assigned_to})

    for person_id in people:
        items = [item for item in facts.items if item.assigned_to == person_id]
        load = known_load(
            items,
            unit=unit,
            relations=facts.relations,
            accounting_level=team.process.accounting_level,
        )
        reservations = [
            reservation
            for reservation in facts.reservations
            if reservation.person_id == person_id and reservation.per_day.unit == unit
        ]
        capacity = (
            reserved_capacity(reservations, day_factors.get(person_id, {}))
            if reservations
            else None
        )
        classification = classify_load(load, capacity, thresholds=team.allocation.thresholds)
        rows.append(
            PersonRow(
                person_id=person_id,
                display_name=names.get(person_id),
                known_load=load.quantity,
                reserved_capacity=capacity,
                utilization=classification.ratio,
                load_class=classification.load_class.value,
                is_lower_bound=classification.is_lower_bound,
                items_eligible=load.counters.eligible or 0,
                items_known=load.counters.known,
                items_missing=load.counters.missing,
                reason=classification.reason,
            )
        )

    unassigned = [item for item in facts.items if not item.assigned_to]
    if unassigned:
        load = known_load(
            unassigned,
            unit=unit,
            relations=facts.relations,
            accounting_level=team.process.accounting_level,
        )
        if load.counters.eligible:
            notes.append(
                f"{load.counters.eligible} itens abertos sem responsável entram na carga da "
                "equipe, mas não em nenhuma pessoa"
            )
            rows.append(
                PersonRow(
                    person_id="(sem responsável)",
                    known_load=load.quantity,
                    load_class="SEM_RESPONSAVEL",
                    items_eligible=load.counters.eligible or 0,
                    items_known=load.counters.known,
                    items_missing=load.counters.missing,
                    reason="itens sem responsável não têm capacidade pessoal comparável",
                )
            )
    return rows
