"""Respostas sintéticas do MCP oficial usadas por coleta, relatório e demo.

Todos os identificadores são fictícios e estáveis, para que as métricas esperadas possam
ser calculadas à mão: a sprint tem 5 dias úteis (14 a 18/09/2026), duas pessoas com 6
unidades/dia e um dia de folga pessoal.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ado_team_compass.mcp.session import FixtureTransport, ToolDescriptor
from ado_team_compass.mcp.session.transport import schema_hash

ORGANIZATION = "contoso-demo"
PROJECT_ID = "proj-demo"
TEAM_ID = "team-demo"
ITERATION_PATH = "Demo\\Sprint 42"
ITERATION_ID = "iter-42"

READ_TOOLS = (
    "core_list_projects",
    "core_list_project_teams",
    "work_get_team_settings",
    "work_list_team_iterations",
    "work_get_team_capacity",
    "work_get_iteration_capacities",
    "wit_list_work_items_for_iteration",
    "wit_get_work_items_batch",
    "wit_get_work_item_type",
)

PERSON_ANA = "person-ana"
PERSON_BRUNO = "person-bruno"


def _field_item(
    item_id: int,
    *,
    item_type: str = "Task",
    state: str = "Committed",
    remaining: float | None = None,
    original: float | None = None,
    completed: float | None = None,
    assigned_to: str | None = PERSON_ANA,
    parent: int | None = None,
    activity: str | None = "Development",
    tags: str | None = None,
    title: str = "Item de demonstração",
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "System.Id": item_id,
        "System.WorkItemType": item_type,
        "System.State": state,
        "System.Title": title,
        "System.AreaPath": "Demo\\Core",
        "System.IterationPath": ITERATION_PATH,
        "System.CreatedDate": "2026-09-10T12:00:00Z",
        "System.ChangedDate": "2026-09-15T09:30:00Z",
        "Microsoft.VSTS.Common.Activity": activity,
    }
    if assigned_to is not None:
        fields["System.AssignedTo"] = {"id": assigned_to, "displayName": assigned_to}
    if remaining is not None:
        fields["Microsoft.VSTS.Scheduling.RemainingWork"] = remaining
    if original is not None:
        fields["Microsoft.VSTS.Scheduling.OriginalEstimate"] = original
    if completed is not None:
        fields["Microsoft.VSTS.Scheduling.CompletedWork"] = completed
    if parent is not None:
        fields["System.Parent"] = parent
    if tags is not None:
        fields["System.Tags"] = tags
    return {"id": item_id, "fields": fields}


#: Itens da sprint sintética. Totais esperados (perfil com capacidade, nível task folha):
#: carga conhecida = 10 + 6 + 8 + 4 = 28 unidades; dois itens abertos sem restante.
WORK_ITEMS: tuple[dict[str, Any], ...] = (
    _field_item(100, item_type="Product Backlog Item", state="Committed", remaining=40),
    _field_item(101, remaining=10, parent=100),
    _field_item(102, remaining=6, parent=100, assigned_to=PERSON_BRUNO),
    _field_item(103, remaining=8, parent=100, tags="impedimento; externo"),
    _field_item(104, remaining=4, parent=100, assigned_to=PERSON_BRUNO),
    _field_item(105, parent=100, original=40),
    _field_item(106, parent=100, assigned_to=PERSON_BRUNO),
    _field_item(107, state="Done", remaining=0, completed=12, parent=100),
    _field_item(108, state="Em análise", remaining=5, parent=100),
)

CAPACITY: dict[str, Any] = {
    "teamCapacities": [
        {
            "teamMember": {"id": PERSON_ANA, "displayName": "Ana"},
            "activities": [{"name": "Development", "capacityPerDay": 6}],
            "daysOff": [{"start": "2026-09-16T00:00:00Z", "end": "2026-09-16T00:00:00Z"}],
        },
        {
            "teamMember": {"id": PERSON_BRUNO, "displayName": "Bruno"},
            "activities": [{"name": "Development", "capacityPerDay": 6}],
            "daysOff": [],
        },
    ],
    "teamDaysOff": [],
}

ITERATIONS: dict[str, Any] = {
    "value": [
        {
            "id": ITERATION_ID,
            "path": ITERATION_PATH,
            "attributes": {
                "startDate": "2026-09-14T00:00:00Z",
                "finishDate": "2026-09-18T00:00:00Z",
            },
        }
    ]
}


def default_responses() -> dict[str, Any]:
    """Respostas completas da organização sintética."""
    return {
        "core_list_projects": {"value": [{"id": PROJECT_ID, "name": "Demo"}]},
        "core_list_project_teams": {"value": [{"id": TEAM_ID, "name": "Core"}]},
        "work_get_team_settings": {
            "teamFieldValues": [{"value": "Demo\\Core", "includeChildren": True}]
        },
        "work_list_team_iterations": ITERATIONS,
        "work_get_team_capacity": CAPACITY,
        "wit_list_work_items_for_iteration": {
            "workItemRelations": [{"target": {"id": item["id"]}} for item in WORK_ITEMS]
        },
        "wit_get_work_items_batch": {"value": list(WORK_ITEMS)},
    }


def transport(
    responses: Mapping[str, Any] | None = None, tools: tuple[str, ...] = READ_TOOLS
) -> FixtureTransport:
    """Transporte de fixture com o catálogo e as respostas sintéticas."""
    return FixtureTransport(
        tools=tuple(
            ToolDescriptor(
                name=name,
                input_schema_hash=schema_hash({"properties": {"project": {"type": "string"}}}),
                input_properties=("project",),
            )
            for name in tools
        ),
        responses=dict(responses or default_responses()),
    )
