"""Conjunto de dados sintético incluído no produto (entrada `demo`).

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

#: Catálogo sintético espelhando o servidor oficial 2.10.0: ferramentas consolidadas por
#: ação, incluindo uma ferramenta mista (leitura e reordenação) e ferramentas de escrita.
CATALOG: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    # ferramenta: (ações anunciadas, propriedades do schema)
    "core_list_projects": ((), ("stateFilter", "top", "skip", "continuationToken")),
    "core_list_project_teams": ((), ("project", "mine", "top", "skip")),
    "work": (
        (
            "list_iterations",
            "list_team_iterations",
            "get_team_settings",
            "get_team_capacity",
            "get_iteration_capacities",
        ),
        ("action", "project", "team", "iterationId", "timeframe", "depth"),
    ),
    "wit_work_item": (
        (
            "get",
            "get_batch",
            "list_comments",
            "my",
            "list_revisions",
            "list_for_iteration",
            "get_type",
        ),
        ("action", "project", "id", "ids", "workItemId", "fields", "team", "iterationId"),
    ),
    "wit_query": (("get", "get_results", "wiql"), ("action", "project", "id", "wiql", "top")),
    # Ferramenta mista: listar é leitura, reordenar é escrita. A allowlist precisa separar.
    "wit_backlog": (("list", "list_work_items", "reorder"), ("action", "project", "team")),
    "wit_work_item_write": ((), ("project", "id")),
    "work_capacity_write": ((), ("project", "team", "iterationId")),
}

READ_TOOLS = tuple(CATALOG)

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
            "teamMember": {
                "id": PERSON_ANA,
                "displayName": "Ana",
                "uniqueName": "ana@empresa.com",
            },
            "activities": [{"name": "Development", "capacityPerDay": 6}],
            "daysOff": [{"start": "2026-09-16T00:00:00Z", "end": "2026-09-16T00:00:00Z"}],
        },
        {
            "teamMember": {
                "id": PERSON_BRUNO,
                "displayName": "Bruno",
                "uniqueName": "bruno@empresa.com",
            },
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


#: Definição de tipo espelhando o formato real: estados com categoria e campos do processo.
WORK_ITEM_TYPE: dict[str, Any] = {
    "name": "Task",
    "referenceName": "Microsoft.VSTS.WorkItemTypes.Task",
    "states": [
        {"name": "New", "category": "Proposed"},
        {"name": "Committed", "category": "InProgress"},
        {"name": "Done", "category": "Completed"},
        {"name": "Removed", "category": "Removed"},
    ],
    "fields": [
        {"referenceName": "Microsoft.VSTS.Scheduling.RemainingWork"},
        {"referenceName": "Microsoft.VSTS.Scheduling.OriginalEstimate"},
        {"referenceName": "Microsoft.VSTS.Scheduling.CompletedWork"},
    ],
}


def default_responses() -> dict[str, Any]:
    """Respostas completas da organização sintética, chaveadas por ferramenta e ação."""
    return {
        "core_list_projects": {"value": [{"id": PROJECT_ID, "name": "Demo"}]},
        "core_list_project_teams": {"value": [{"id": TEAM_ID, "name": "Core"}]},
        "work:get_team_settings": {
            "teamFieldValues": [{"value": "Demo\\Core", "includeChildren": True}]
        },
        "work:list_team_iterations": ITERATIONS,
        "work:get_team_capacity": CAPACITY,
        "wit_work_item:list_for_iteration": {
            "workItemRelations": [{"target": {"id": item["id"]}} for item in WORK_ITEMS]
        },
        "wit_work_item:get_batch": {"value": list(WORK_ITEMS)},
        "wit_work_item:get_type": WORK_ITEM_TYPE,
    }


def transport(
    responses: Mapping[str, Any] | None = None,
    tools: tuple[str, ...] = READ_TOOLS,
    actions_override: Mapping[str, tuple[str, ...]] | None = None,
) -> FixtureTransport:
    """Transporte de fixture com o catálogo e as respostas sintéticas.

    `actions_override` reduz as ações anunciadas por uma ferramenta consolidada, para exercitar
    catálogo parcial sem remover a ferramenta inteira.
    """
    overrides = dict(actions_override or {})
    descriptors = []
    for name in tools:
        actions, properties = CATALOG.get(name, ((), ("project",)))
        if name in overrides:
            actions = overrides[name]
        schema: dict[str, Any] = {"properties": {item: {"type": "string"} for item in properties}}
        if actions:
            schema["properties"]["action"] = {"type": "string", "enum": list(actions)}
        descriptors.append(
            ToolDescriptor(
                name=name,
                input_schema_hash=schema_hash(schema),
                input_properties=tuple(sorted(schema["properties"])),
                action_parameter="action" if actions else None,
                actions=actions,
            )
        )
    return FixtureTransport(
        tools=tuple(descriptors), responses=dict(responses or default_responses())
    )


def demo_config_document() -> dict[str, Any]:
    """Configuração sintética completa, com perfil de sprint com capacidade em horas."""
    return {
        "schema_version": "1.0",
        "connections": [
            {
                "alias": "demo",
                "organization": ORGANIZATION,
                "server": {"name": "azure-devops", "transport": "http"},
            }
        ],
        "teams": [
            {
                "alias": "demo",
                "connection": "demo",
                "project_id": PROJECT_ID,
                "team_id": TEAM_ID,
                "project_name": "Demo",
                "team_name": "Core",
                "profile": "sprint_with_capacity",
                "capabilities": ["current_status", "allocation"],
                "scope": {"area_paths": ["Demo\\Core"], "include_descendants": True},
                "process": {
                    "state_categories": {
                        "New": "proposed",
                        "Committed": "in_progress",
                        "Done": "completed",
                        "Removed": "removed",
                    },
                    "impediment_source": "tag:impedimento",
                },
                "calendar": {"timezone": "America/Sao_Paulo"},
                "allocation": {"unit": "hours"},
            }
        ],
    }


def demo_team() -> Any:
    """Equipe sintética já resolvida pela precedência de configuração."""
    from ado_team_compass.config import resolve_config

    return resolve_config(demo_config_document()).config.teams[0]
