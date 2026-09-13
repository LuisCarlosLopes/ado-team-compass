"""Coleta da situação atual de uma equipe (plano 4.1.3, 4.2 e T05).

A coleta de fontes diferentes não é um snapshot transacional: cada fonte carrega sua
proveniência e seu horário. Fonte indisponível ou parcial chega identificada até a saída,
e nenhuma contagem incompleta é apresentada como total.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from ado_team_compass.adapters.ado_mcp import AdoMcpClient, Operation
from ado_team_compass.collect.normalization import (
    IdentityIndex,
    NormalizedCapacity,
    NormalizedItem,
    entries,
    hierarchy_relations,
    iteration_contains,
    normalize_capacity,
    normalize_iteration_window,
    normalize_team_days_off,
    normalize_work_item,
)
from ado_team_compass.contracts.common import Provenance, Window
from ado_team_compass.contracts.config import TeamConfig
from ado_team_compass.contracts.facts import FactSet, Person, WorkItemFact, WorkItemRelation
from ado_team_compass.errors import CapabilityUnavailable, CollectError
from ado_team_compass.metrics.calendar import resolve_window
from ado_team_compass.metrics.cross_team import deduplicate_items

__all__ = ["BATCH_SIZE", "CollectionResult", "collect_current_status"]

#: Tamanho de lote na hidratação de itens; o servidor oficial limita lotes grandes.
BATCH_SIZE = 200

#: Campos de sistema sempre pedidos: sem `fields`, o servidor devolve um conjunto mínimo.
SYSTEM_FIELDS = (
    "System.Id",
    "System.WorkItemType",
    "System.State",
    "System.Title",
    "System.AssignedTo",
    "System.AreaPath",
    "System.IterationPath",
    "System.Parent",
    "System.Tags",
    "System.CreatedDate",
    "System.ChangedDate",
    "Microsoft.VSTS.Common.Activity",
    "Microsoft.VSTS.Scheduling.StartDate",
    "Microsoft.VSTS.Scheduling.TargetDate",
    "Microsoft.VSTS.Scheduling.FinishDate",
    "Microsoft.VSTS.Scheduling.DueDate",
)


def requested_fields(team: TeamConfig) -> tuple[str, ...]:
    """Campos pedidos na hidratação: os de sistema mais os configurados no perfil."""
    configured = (
        team.process.remaining_work_field,
        team.process.original_estimate_field,
        team.process.completed_work_field,
        team.process.story_points_field,
    )
    names = [*SYSTEM_FIELDS, *(name for name in configured if name)]
    return tuple(dict.fromkeys(names))


@dataclass
class CollectionResult:
    """Fatos coletados, janela resolvida e cobertura da coleta."""

    team_alias: str
    as_of: datetime
    facts: FactSet
    window: Window | None = None
    iteration_path: str | None = None
    partial_sources: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    call_log: tuple[Any, ...] = field(default_factory=tuple)

    @property
    def is_complete(self) -> bool:
        return not self.partial_sources


def collect_current_status(
    client: AdoMcpClient,
    team: TeamConfig,
    *,
    organization: str,
    as_of: datetime,
    iteration_path: str | None = None,
) -> CollectionResult:
    """Coleta iteração, itens e capacidade da equipe no escopo configurado."""
    partial: list[str] = []
    reasons: list[str] = []
    collected_at = as_of

    window, resolved_path, iteration_id = _resolve_iteration(
        client, team, as_of=as_of, iteration_path=iteration_path, partial=partial, reasons=reasons
    )

    # A capacidade vem primeiro porque é ela que traz o ID estável de cada pessoa; os itens
    # referenciam a pessoa por texto e precisam ser reconciliados com esse ID.
    capacity = _collect_capacity(
        client, team, iteration_id=iteration_id, partial=partial, reasons=reasons
    )

    items, relations, item_reasons, items_partial = _collect_items(
        client,
        team,
        organization=organization,
        iteration_path=resolved_path,
        iteration_id=iteration_id,
        collected_at=collected_at,
        identities=capacity.identities,
    )
    reasons.extend(item_reasons)
    partial.extend(items_partial)

    people = _merge_people(capacity.people, items)
    facts = FactSet(
        as_of=as_of,
        people=people,
        reservations=capacity.reservations,
        days_off=capacity.days_off,
        items=items,
        relations=relations,
        partial_sources=tuple(dict.fromkeys(partial)),
        reasons=tuple(dict.fromkeys(reasons)),
    )
    return CollectionResult(
        team_alias=team.alias,
        as_of=as_of,
        facts=facts,
        window=window,
        iteration_path=resolved_path,
        partial_sources=tuple(dict.fromkeys(partial)),
        reasons=tuple(dict.fromkeys(reasons)),
        call_log=tuple(client.call_log),
    )


def _resolve_iteration(
    client: AdoMcpClient,
    team: TeamConfig,
    *,
    as_of: datetime,
    iteration_path: str | None,
    partial: list[str],
    reasons: list[str],
) -> tuple[Window | None, str | None, str | None]:
    """Escolhe a iteração pedida, a configurada ou a que contém `as_of`."""
    try:
        payload = client.call(
            Operation.LIST_ITERATIONS, {"project": team.project_id, "team": team.team_id}
        )
    except CapabilityUnavailable as error:
        partial.append("iterations")
        reasons.append(f"iterações indisponíveis: {error.message}")
        return None, iteration_path, None

    wanted = iteration_path or (team.scope.iterations[0] if team.scope.iterations else None)
    candidates: list[tuple[str | None, date | None, date | None, str | None]] = []
    for entry in entries(payload, "iterations"):
        path, start, finish = normalize_iteration_window(entry)
        identifier = entry.get("id") if isinstance(entry.get("id"), str) else None
        candidates.append((path, start, finish, identifier))

    chosen: tuple[str | None, date | None, date | None, str | None] | None = None
    if wanted is not None:
        chosen = next((entry for entry in candidates if entry[0] == wanted), None)
        if chosen is None:
            reasons.append(f"a iteração {wanted!r} não apareceu na resposta do MCP")
    if chosen is None:
        chosen = next(
            (
                entry
                for entry in candidates
                if iteration_contains((entry[1], entry[2]), as_of, team.calendar.timezone)
            ),
            None,
        )
    if chosen is None:
        partial.append("iterations")
        undated = [entry[0] for entry in candidates if entry[1] is None or entry[2] is None]
        if undated:
            reasons.append(
                "a resposta não informou datas de início e fim para: "
                + ", ".join(str(path) for path in undated)
            )
        reasons.append("nenhuma iteração conhecida contém o instante de referência")
        return None, wanted, None

    path, start, finish, identifier = chosen
    if start is None or finish is None:
        partial.append("iterations")
        reasons.append(f"a iteração {path!r} não informou datas de início e fim")
        return None, path, identifier
    window = resolve_window(start, finish, timezone=team.calendar.timezone, end_inclusive=True)
    return window, path, identifier


def _collect_items(
    client: AdoMcpClient,
    team: TeamConfig,
    *,
    organization: str,
    iteration_path: str | None,
    iteration_id: str | None,
    collected_at: datetime,
    identities: IdentityIndex | None = None,
) -> tuple[tuple[WorkItemFact, ...], tuple[Any, ...], list[str], list[str]]:
    reasons: list[str] = []
    partial: list[str] = []
    if iteration_path is None:
        partial.append("work_items")
        reasons.append("sem iteração resolvida, os itens da sprint não foram coletados")
        return (), (), reasons, partial
    if iteration_id is None:
        partial.append("work_items")
        reasons.append(
            "a iteração resolvida não trouxe identificador: a listagem de itens da sprint "
            "exige o ID da iteração"
        )
        return (), (), reasons, partial

    arguments: dict[str, Any] = {
        "project": team.project_id,
        "team": team.team_id,
        "iterationId": iteration_id,
    }
    if team.scope.area_paths:
        arguments["areaPaths"] = list(team.scope.area_paths)
        arguments["includeDescendants"] = team.scope.include_descendants

    identifiers: list[int] = []
    linked: list[WorkItemRelation] = []
    try:
        pages = client.paginate(
            Operation.LIST_ITERATION_WORK_ITEMS,
            arguments,
            items_fields=("workItemRelations", "workItems", "value"),
        )
        for page in pages:
            for entry in entries(page, "workItemRelations", "workItems"):
                target = entry.get("target") if isinstance(entry.get("target"), dict) else entry
                target_id = _identifier(target.get("id") if isinstance(target, dict) else None)
                if target_id is None:
                    continue
                identifiers.append(target_id)
                # A própria listagem traz a hierarquia da iteração; ela é usada como
                # relação observada, sem depender de campo por item.
                source = entry.get("source")
                relation = entry.get("rel")
                source_id = _identifier(source.get("id") if isinstance(source, dict) else None)
                if source_id is not None and isinstance(relation, str) and "Hierarchy" in relation:
                    linked.append(WorkItemRelation(parent_id=source_id, child_id=target_id))
    except CapabilityUnavailable as error:
        partial.append("work_items")
        reasons.append(f"listagem de itens indisponível: {error.message}")
        return (), (), reasons, partial
    except CollectError as error:
        partial.append("work_items")
        reasons.append(f"listagem de itens incompleta: {error.message}")
        return (), (), reasons, partial

    unique_ids = list(dict.fromkeys(identifiers))
    normalized: list[NormalizedItem] = []
    provenance_base = {"source": "mcp", "action": "read", "collected_at": collected_at}

    for start in range(0, len(unique_ids), BATCH_SIZE):
        batch = unique_ids[start : start + BATCH_SIZE]
        try:
            payload = client.call(
                Operation.GET_WORK_ITEMS_BATCH,
                {
                    "project": team.project_id,
                    "ids": batch,
                    "fields": list(requested_fields(team)),
                },
            )
        except CapabilityUnavailable as error:
            partial.append("work_items")
            reasons.append(f"hidratação de itens indisponível: {error.message}")
            break
        except CollectError as error:
            partial.append("work_items")
            reasons.append(f"lote de itens não hidratado: {error.message}")
            break
        returned = entries(payload, "workItems")
        if len(returned) < len(batch):
            partial.append("work_items")
            reasons.append(
                f"o lote pediu {len(batch)} itens e recebeu {len(returned)}: cobertura parcial"
            )
        for entry in returned:
            provenance = Provenance(
                **provenance_base,
                tool="get_work_items_batch",
                references=(f"evidence/items/{entry.get('id')}.json",),
            )
            item = normalize_work_item(
                entry,
                team=team,
                organization=organization,
                provenance=provenance,
                identities=identities,
            )
            if item is None:
                reasons.append("um item veio sem ID e foi descartado")
                continue
            normalized.append(item)
            reasons.extend(item.reasons)

    facts, overlapping = deduplicate_items([item.fact for item in normalized])
    relations = tuple(dict.fromkeys((*linked, *hierarchy_relations(normalized))))
    if overlapping:
        reasons.append(
            "itens repetidos na resposta foram contados uma única vez: "
            + ", ".join(str(item_id) for item_id in overlapping)
        )
    return facts, relations, reasons, partial


def _identifier(value: Any) -> int | None:
    """Converte o ID de um item, aceitando número ou string numérica."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _collect_capacity(
    client: AdoMcpClient,
    team: TeamConfig,
    *,
    iteration_id: str | None,
    partial: list[str],
    reasons: list[str],
) -> NormalizedCapacity:
    """Capacidade e folgas; ausência da ferramenta torna a carga não aplicável, não zero."""
    empty = normalize_capacity(None, team=team)
    arguments: dict[str, Any] = {"project": team.project_id, "team": team.team_id}
    if iteration_id:
        arguments["iterationId"] = iteration_id
    try:
        payload = client.call(Operation.GET_TEAM_CAPACITY, arguments)
    except CapabilityUnavailable as error:
        partial.append("capacity")
        reasons.append(f"capacidade indisponível: {error.message}")
        return empty
    except CollectError as error:
        partial.append("capacity")
        reasons.append(f"capacidade não coletada: {error.message}")
        return empty

    capacity = normalize_capacity(payload, team=team)
    reasons.extend(capacity.reasons)
    team_days_off, day_reasons = normalize_team_days_off(payload, team_id=team.team_id)
    reasons.extend(day_reasons)
    if day_reasons:
        partial.append("team_days_off")
    return NormalizedCapacity(
        reservations=capacity.reservations,
        days_off=(*capacity.days_off, *team_days_off),
        people=capacity.people,
        reasons=capacity.reasons,
        identities=capacity.identities,
    )


def _merge_people(
    from_capacity: Sequence[Person], items: Sequence[WorkItemFact]
) -> tuple[Person, ...]:
    """Pessoas da capacidade mais responsáveis de itens, sem duplicar identidade."""
    people: dict[str, Person] = {person.id: person for person in from_capacity}
    for item in items:
        if item.assigned_to and item.assigned_to not in people:
            people[item.assigned_to] = Person(
                id=item.assigned_to, teams=tuple(item.team_memberships)
            )
    return tuple(people.values())
