"""Fatos normalizados coletados pelo MCP oficial (contrato de `facts.json`)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import Field

from ado_team_compass.contracts.common import Provenance, Quantity, StrictModel
from ado_team_compass.contracts.config import StateCategory

__all__ = [
    "CapacityReservation",
    "DayOff",
    "FactSet",
    "Person",
    "WorkItemFact",
    "WorkItemRelation",
]


class Person(StrictModel):
    """Pessoa identificada pela fonte; identidade é por ID opaco, não por nome."""

    id: str
    display_name: str | None = None
    teams: tuple[str, ...] = ()


class CapacityReservation(StrictModel):
    """Capacidade reservada por equipe/atividade. Reserva não prova disponibilidade."""

    person_id: str
    team_id: str
    activity: str | None = None
    per_day: Quantity


class DayOff(StrictModel):
    """Folga de equipe ou pessoal, com fim exclusivo para união sem desconto duplicado."""

    person_id: str | None = None
    team_id: str | None = None
    start: date
    end: date
    fraction: Decimal | None = Field(default=None, gt=0, le=1)
    source: str


class WorkItemRelation(StrictModel):
    parent_id: int
    child_id: int
    relation: str = "hierarchy"


class WorkItemFact(StrictModel):
    """Item de trabalho normalizado. Campos ausentes permanecem nulos, nunca zero."""

    id: int
    organization: str
    project_id: str
    item_type: str
    state: str
    state_category: StateCategory | None = None
    title: str | None = None
    assigned_to: str | None = None
    area_path: str | None = None
    iteration_path: str | None = None
    remaining_work: Quantity | None = None
    original_estimate: Quantity | None = None
    completed_work: Quantity | None = None
    story_points: Decimal | None = None
    activity: str | None = None
    is_leaf: bool | None = None
    blocked: bool | None = None
    start_date: date | None = None
    target_date: date | None = None
    created_at: datetime | None = None
    changed_at: datetime | None = None
    team_memberships: tuple[str, ...] = ()
    provenance: Provenance


class FactSet(StrictModel):
    """Conjunto de fatos de uma coleta, com cobertura e motivos por fonte."""

    as_of: datetime
    people: tuple[Person, ...] = ()
    reservations: tuple[CapacityReservation, ...] = ()
    days_off: tuple[DayOff, ...] = ()
    items: tuple[WorkItemFact, ...] = ()
    relations: tuple[WorkItemRelation, ...] = ()
    partial_sources: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
