"""Consolidação entre equipes por pessoa (plano 4.1.4, arquitetura D04).

Regras implementadas:

- carga é deduplicada por organização + ID do item; itens sobrepostos aparecem como tais;
- consolidação ocorre na mesma janela solicitada, com a união dos dias elegíveis;
- somar reservas de várias equipes não prova disponibilidade total da pessoa;
- disponibilidade global só é usada quando configurada explicitamente para a pessoa e a
  janela; sem ela, a utilização global permanece nula, sem inferir jornada padrão;
- o universo observado é a lista de equipes selecionadas e acessíveis, e nada além dela.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from ado_team_compass.contracts.common import Quantity
from ado_team_compass.contracts.config import PersonalAvailability
from ado_team_compass.contracts.facts import CapacityReservation, WorkItemFact, WorkItemRelation
from ado_team_compass.metrics.allocation import KnownLoad, known_load
from ado_team_compass.metrics.calendar import reserved_capacity

__all__ = ["PersonConsolidation", "consolidate_person", "deduplicate_items"]


@dataclass(frozen=True)
class PersonConsolidation:
    """Visão consolidada de uma pessoa nas equipes observadas."""

    person_id: str
    observed_teams: tuple[str, ...]
    reservations_by_team: Mapping[str, Quantity]
    reserved_total: Quantity
    personal_availability: Quantity | None
    load: KnownLoad
    global_utilization: Decimal | None
    overlapping_item_ids: tuple[int, ...] = ()
    limitations: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_over_reserved(self) -> bool:
        """Reservas somadas acima da disponibilidade pessoal informada."""
        if self.personal_availability is None or self.personal_availability.value is None:
            return False
        if self.reserved_total.value is None:
            return False
        return self.reserved_total.value > self.personal_availability.value


def deduplicate_items(
    items: Sequence[WorkItemFact],
) -> tuple[tuple[WorkItemFact, ...], tuple[int, ...]]:
    """Mantém um fato por organização + ID e devolve os IDs vistos em mais de um recorte."""
    unique: dict[tuple[str, int], WorkItemFact] = {}
    overlapping: list[int] = []
    for item in items:
        key = (item.organization, item.id)
        if key in unique:
            existing = unique[key]
            memberships = tuple(dict.fromkeys((*existing.team_memberships, *item.team_memberships)))
            unique[key] = existing.model_copy(update={"team_memberships": memberships})
            if item.id not in overlapping:
                overlapping.append(item.id)
            continue
        unique[key] = item
    for item in unique.values():
        if len(item.team_memberships) > 1 and item.id not in overlapping:
            overlapping.append(item.id)
    return tuple(unique.values()), tuple(sorted(overlapping))


def consolidate_person(
    person_id: str,
    *,
    observed_teams: Sequence[str],
    reservations: Sequence[CapacityReservation],
    day_factors_by_team: Mapping[str, Mapping[date, Decimal]],
    items: Sequence[WorkItemFact] = (),
    relations: Sequence[WorkItemRelation] = (),
    unit: str,
    accounting_level: str | None = None,
    personal_availability: PersonalAvailability | None = None,
    limitations: Sequence[str] = (),
) -> PersonConsolidation:
    """Consolida reservas, carga deduplicada e utilização global de uma pessoa."""
    notes = list(limitations)
    reservations_by_team: dict[str, Quantity] = {}
    reserved_total = Quantity(value=None, unit=unit)

    for team_id in observed_teams:
        team_reservations = [
            reservation
            for reservation in reservations
            if reservation.person_id == person_id and reservation.team_id == team_id
        ]
        if not team_reservations:
            notes.append(f"equipe {team_id} não expõe reserva conhecida para esta pessoa")
            continue
        units = {reservation.per_day.unit for reservation in team_reservations}
        if units != {unit}:
            notes.append(
                f"equipe {team_id} reserva em {sorted(units)}, incompatível com {unit!r}: "
                "agregação indisponível"
            )
            continue
        team_total = reserved_capacity(team_reservations, day_factors_by_team.get(team_id, {}))
        reservations_by_team[team_id] = team_total
        reserved_total = reserved_total.add(team_total)

    unique_items, overlapping = deduplicate_items(
        [item for item in items if item.assigned_to == person_id]
    )
    load = known_load(
        unique_items, unit=unit, relations=relations, accounting_level=accounting_level
    )

    availability_quantity: Quantity | None = None
    utilization: Decimal | None = None
    if personal_availability is None:
        notes.append(
            "disponibilidade global não informada para esta pessoa: utilização global nula"
        )
    elif personal_availability.unit != unit:
        notes.append(
            f"disponibilidade informada em {personal_availability.unit!r} não é comparável "
            f"com {unit!r} sem fator explícito"
        )
    else:
        eligible_days = {day for factors in day_factors_by_team.values() for day in factors}
        available_days = sum(
            (
                max(factors.get(day, Decimal(0)) for factors in day_factors_by_team.values())
                for day in eligible_days
            ),
            Decimal(0),
        )
        availability_quantity = Quantity(
            value=personal_availability.per_day * available_days, unit=unit
        )
        if load.quantity.value is None:
            notes.append("sem carga conhecida, a utilização global permanece nula")
        elif not availability_quantity.value:
            notes.append("disponibilidade global igual a zero na janela: sem percentual")
        else:
            utilization = load.quantity.value / availability_quantity.value
            if not load.is_complete:
                notes.append("utilização global é parcial: há itens abertos sem trabalho restante")

    if overlapping:
        notes.append(
            "itens sobrepostos entre equipes contados uma única vez: "
            + ", ".join(str(item_id) for item_id in overlapping)
        )
    notes.append(
        "universo observado limitado às equipes selecionadas e acessíveis: "
        + ", ".join(observed_teams)
    )

    return PersonConsolidation(
        person_id=person_id,
        observed_teams=tuple(observed_teams),
        reservations_by_team=reservations_by_team,
        reserved_total=reserved_total,
        personal_availability=availability_quantity,
        load=load,
        global_utilization=utilization,
        overlapping_item_ids=overlapping,
        limitations=tuple(dict.fromkeys(notes)),
    )
