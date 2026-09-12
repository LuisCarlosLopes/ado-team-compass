"""Normalização das respostas do MCP oficial em fatos tipados.

Nada é inventado: campo ausente permanece ausente, unidade é preservada como veio, estado
sem categoria mapeada não é classificado por palpite e todo fato carrega proveniência.
Texto de item é dado, nunca instrução.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from ado_team_compass.contracts.common import Provenance, Quantity
from ado_team_compass.contracts.config import TeamConfig
from ado_team_compass.contracts.facts import (
    CapacityReservation,
    DayOff,
    Person,
    WorkItemFact,
    WorkItemRelation,
)

__all__ = [
    "NormalizedCapacity",
    "NormalizedItem",
    "entries",
    "normalize_capacity",
    "normalize_iteration_window",
    "normalize_team_days_off",
    "normalize_work_item",
]

_ITEM_ID_KEYS = ("id", "workItemId", "Id")


def entries(payload: Any, *keys: str) -> list[Mapping[str, Any]]:
    """Extrai a lista de registros de um payload sem presumir o formato do servidor."""
    if payload is None:
        return []
    if isinstance(payload, Mapping):
        for key in (*keys, "value", "items", "workItems", "teamCapacities", "capacities"):
            nested = payload.get(key)
            if isinstance(nested, list):
                return [entry for entry in nested if isinstance(entry, Mapping)]
        return [payload]
    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, Mapping)]
    return []


def _fields(entry: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = entry.get("fields")
    if isinstance(nested, Mapping):
        return nested
    return entry


def _text(entry: Mapping[str, Any], *names: str) -> str | None:
    source = _fields(entry)
    for name in names:
        value = source.get(name) if name in source else entry.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, Mapping):
            for key in ("displayName", "uniqueName", "name", "id"):
                nested = value.get(key)
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()
    return None


def _decimal(value: Any) -> Decimal | None:
    """Converte números e strings numéricas; valores não numéricos ficam ausentes."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int | float):
        return Decimal(str(value))
    if isinstance(value, str) and value.strip():
        try:
            return Decimal(value.strip())
        except InvalidOperation:
            return None
    return None


def _moment(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _day(value: Any) -> date | None:
    moment = _moment(value)
    return moment.date() if moment else None


class NormalizedItem:
    """Item normalizado com os motivos de qualquer campo que não pôde ser usado."""

    __slots__ = ("fact", "parent_id", "reasons")

    def __init__(
        self, fact: WorkItemFact, *, parent_id: int | None, reasons: tuple[str, ...]
    ) -> None:
        self.fact = fact
        self.parent_id = parent_id
        self.reasons = reasons


def normalize_work_item(
    entry: Mapping[str, Any],
    *,
    team: TeamConfig,
    organization: str,
    provenance: Provenance,
) -> NormalizedItem | None:
    """Converte um item do MCP em fato, preservando ausências e unidades."""
    identifier = None
    for key in _ITEM_ID_KEYS:
        identifier = _decimal(entry.get(key))
        if identifier is not None:
            break
    if identifier is None:
        return None

    fields = _fields(entry)
    reasons: list[str] = []
    item_id = int(identifier)
    state = _text(entry, "System.State", "state") or ""
    category = team.process.state_categories.get(state)
    if state and category is None:
        reasons.append(f"item {item_id}: estado {state!r} sem categoria mapeada")

    unit = team.allocation.unit
    remaining = _quantity(fields, team.process.remaining_work_field, unit)
    original = _quantity(fields, team.process.original_estimate_field, unit)
    completed = _quantity(fields, team.process.completed_work_field, unit)
    if team.process.remaining_work_field and remaining is None:
        reasons.append(f"item {item_id}: sem valor em {team.process.remaining_work_field}")

    parent_raw = _decimal(fields.get("System.Parent") or entry.get("parentId"))
    blocked_tag = _text(entry, "System.Tags", "tags")
    blocked = None
    if team.process.blocked_states:
        blocked = state in team.process.blocked_states
    source = team.process.impediment_source
    if blocked is None and source and source.startswith("tag:"):
        # Com a origem de impedimento configurada por tag, a ausência da tag é informação:
        # o item não está marcado como impedido.
        blocked = source.removeprefix("tag:").lower() in (blocked_tag or "").lower()

    fact = WorkItemFact(
        id=item_id,
        organization=organization,
        project_id=team.project_id,
        item_type=_text(entry, "System.WorkItemType", "workItemType") or "desconhecido",
        state=state or "desconhecido",
        state_category=category,
        title=_text(entry, "System.Title", "title"),
        assigned_to=_text(entry, "System.AssignedTo", "assignedTo"),
        area_path=_text(entry, "System.AreaPath", "areaPath"),
        iteration_path=_text(entry, "System.IterationPath", "iterationPath"),
        remaining_work=remaining,
        original_estimate=original,
        completed_work=completed,
        story_points=_decimal(fields.get(team.process.story_points_field or "")),
        activity=_text(entry, "Microsoft.VSTS.Common.Activity", "activity"),
        blocked=blocked,
        created_at=_moment(fields.get("System.CreatedDate")),
        changed_at=_moment(fields.get("System.ChangedDate")),
        team_memberships=(team.team_id,),
        provenance=provenance,
    )
    return NormalizedItem(
        fact,
        parent_id=int(parent_raw) if parent_raw is not None else None,
        reasons=tuple(reasons),
    )


def _quantity(fields: Mapping[str, Any], field_name: str | None, unit: str) -> Quantity | None:
    if not field_name:
        return None
    if field_name not in fields:
        return None
    value = _decimal(fields.get(field_name))
    if value is None:
        return None
    return Quantity(value=value, unit=unit)


class NormalizedCapacity:
    """Reservas, folgas pessoais e pessoas extraídas da capacidade da equipe."""

    __slots__ = ("days_off", "people", "reasons", "reservations")

    def __init__(
        self,
        *,
        reservations: tuple[CapacityReservation, ...],
        days_off: tuple[DayOff, ...],
        people: tuple[Person, ...],
        reasons: tuple[str, ...],
    ) -> None:
        self.reservations = reservations
        self.days_off = days_off
        self.people = people
        self.reasons = reasons


def normalize_capacity(payload: Any, *, team: TeamConfig) -> NormalizedCapacity:
    """Converte capacidade por pessoa/atividade e folgas pessoais, preservando a unidade."""
    reservations: list[CapacityReservation] = []
    days_off: list[DayOff] = []
    people: list[Person] = []
    reasons: list[str] = []
    unit = team.allocation.unit

    for entry in entries(payload, "teamCapacities", "capacities"):
        person_id = _person_id(entry)
        if person_id is None:
            reasons.append("uma capacidade veio sem identificação de pessoa e foi ignorada")
            continue
        people.append(
            Person(
                id=person_id,
                display_name=_person_name(entry),
                teams=(team.team_id,),
            )
        )
        activities = entry.get("activities")
        activity_entries = activities if isinstance(activities, list) else []
        if not activity_entries:
            reasons.append(f"pessoa {person_id}: nenhuma atividade com capacidade informada")
        for activity in activity_entries:
            if not isinstance(activity, Mapping):
                continue
            per_day = _decimal(activity.get("capacityPerDay"))
            reservations.append(
                CapacityReservation(
                    person_id=person_id,
                    team_id=team.team_id,
                    activity=_text(activity, "name", "activity"),
                    per_day=Quantity(value=per_day, unit=unit),
                )
            )
            if per_day is None:
                reasons.append(f"pessoa {person_id}: capacidade diária ausente")
        days_off.extend(_days_off(entry.get("daysOff"), person_id=person_id, reasons=reasons))
    return NormalizedCapacity(
        reservations=tuple(reservations),
        days_off=tuple(days_off),
        people=tuple(people),
        reasons=tuple(dict.fromkeys(reasons)),
    )


def _person_id(entry: Mapping[str, Any]) -> str | None:
    """Identidade opaca da pessoa; nome nunca substitui o ID."""
    member = entry.get("teamMember")
    if isinstance(member, Mapping):
        for key in ("id", "uniqueName", "descriptor"):
            value = member.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    for key in ("personId", "memberId", "id"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _person_name(entry: Mapping[str, Any]) -> str | None:
    member = entry.get("teamMember")
    if isinstance(member, Mapping):
        return _text(member, "displayName", "uniqueName")
    return _text(entry, "displayName")


def _days_off(
    raw: Any,
    *,
    person_id: str | None = None,
    team_id: str | None = None,
    reasons: list[str] | None = None,
) -> list[DayOff]:
    """Folgas com fim exclusivo; período sem datas válidas é reportado, não assumido."""
    results: list[DayOff] = []
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, Mapping):
            continue
        start = _day(entry.get("start") or entry.get("startDate"))
        end = _day(entry.get("end") or entry.get("endDate"))
        if start is None or end is None:
            if reasons is not None:
                owner = person_id or team_id or "equipe"
                reasons.append(f"{owner}: folga sem datas válidas foi ignorada")
            continue
        results.append(
            DayOff(
                person_id=person_id,
                team_id=team_id,
                start=start,
                # A fonte usa fim inclusivo; o contrato interno usa fim exclusivo.
                end=end + timedelta(days=1),
                source="mcp:capacity",
            )
        )
    return results


def normalize_team_days_off(
    payload: Any, *, team_id: str
) -> tuple[tuple[DayOff, ...], tuple[str, ...]]:
    """Folgas da equipe inteira, quando a resposta as expuser."""
    reasons: list[str] = []
    raw: Any = None
    if isinstance(payload, Mapping):
        raw = payload.get("teamDaysOff") or payload.get("daysOff")
    elif isinstance(payload, list):
        raw = payload
    if raw is None:
        return (), ("folgas da equipe não vieram na resposta do MCP",)
    return tuple(_days_off(raw, team_id=team_id, reasons=reasons)), tuple(reasons)


def normalize_iteration_window(
    entry: Mapping[str, Any],
) -> tuple[str | None, date | None, date | None]:
    """Caminho, início e fim (inclusivo, como a fonte informa) de uma iteração."""
    attributes = entry.get("attributes")
    source: Mapping[str, Any] = attributes if isinstance(attributes, Mapping) else entry
    path = _text(entry, "path", "name", "iterationPath")
    start = _day(source.get("startDate") or source.get("start"))
    finish = _day(source.get("finishDate") or source.get("endDate") or source.get("finish"))
    return path, start, finish


def iteration_contains(
    window: tuple[date | None, date | None], moment: datetime, timezone: str
) -> bool:
    """Indica se o instante cai na iteração, resolvendo a data no timezone configurado."""
    from zoneinfo import ZoneInfo

    start, finish = window
    if start is None or finish is None:
        return False
    local = moment.astimezone(ZoneInfo(timezone)).date()
    return start <= local <= finish


def person_ids(items: Sequence[WorkItemFact]) -> tuple[str, ...]:
    """Pessoas referenciadas por itens, em ordem estável."""
    return tuple(dict.fromkeys(item.assigned_to for item in items if item.assigned_to))


def hierarchy_relations(items: Sequence[NormalizedItem]) -> tuple[WorkItemRelation, ...]:
    """Relações de hierarquia derivadas de `System.Parent` dos itens coletados."""
    return tuple(
        WorkItemRelation(parent_id=item.parent_id, child_id=item.fact.id)
        for item in items
        if item.parent_id is not None
    )
