"""Allowlist por ferramenta **e ação**, com negativa por padrão (contrato MCP, plano 5.9).

O servidor oficial consolida operações em poucas ferramentas selecionadas por um parâmetro de
ação, e algumas delas são mistas: `wit_backlog` aceita `list` (leitura) e `reorder` (escrita).
Por isso autorizar uma ferramenta não autoriza suas ações: cada operação lógica declara a
ferramenta **e** a ação exata que pode usar, e qualquer ação com semântica de escrita é
recusada mesmo que o catálogo a ofereça.

Os pares abaixo foram verificados no catálogo do servidor oficial `@azure-devops/mcp@2.10.0`
em 13/09/2026 (40 ferramentas). Nomes de versões anteriores permanecem como candidatos de
compatibilidade, marcados como não verificados.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

__all__ = [
    "READ_ALLOWLIST",
    "VERIFIED_CATALOG",
    "WRITE_VERBS",
    "Operation",
    "OperationSpec",
    "ToolAction",
    "is_write_like",
]

#: Catálogo em que os pares ferramenta/ação abaixo foram verificados.
VERIFIED_CATALOG = "@azure-devops/mcp@2.10.0"


class Operation(StrEnum):
    """Operações lógicas de leitura que o produto precisa executar."""

    LIST_PROJECTS = "list_projects"
    LIST_TEAMS = "list_teams"
    GET_TEAM_SETTINGS = "get_team_settings"
    LIST_ITERATIONS = "list_iterations"
    GET_TEAM_CAPACITY = "get_team_capacity"
    GET_ITERATION_CAPACITIES = "get_iteration_capacities"
    LIST_ITERATION_WORK_ITEMS = "list_iteration_work_items"
    GET_WORK_ITEMS_BATCH = "get_work_items_batch"
    GET_WORK_ITEM_TYPE = "get_work_item_type"
    LIST_WORK_ITEM_REVISIONS = "list_work_item_revisions"
    GET_QUERY_RESULTS = "get_query_results"


#: Verbos que caracterizam escrita, aplicados ao nome da ferramenta e ao nome da ação.
WRITE_VERBS = (
    "create",
    "update",
    "delete",
    "remove",
    "add",
    "set",
    "assign",
    "reorder",
    "move",
    "link",
    "unlink",
    "comment",
    "patch",
    "put",
    "post",
    "write",
    "close",
    "resolve",
    "approve",
    "publish",
    "upsert",
    "run",
    "queue",
    "trigger",
)


def is_write_like(name: str) -> bool:
    """Indica se um nome de ferramenta ou de ação contém verbo de escrita.

    A comparação é por segmento para não recusar leitura por coincidência de substring:
    `list_revisions` não contém verbo de escrita, `backlog_reorder` contém.
    """
    segments = {segment for segment in name.lower().replace("-", "_").split("_") if segment}
    return bool(segments & set(WRITE_VERBS))


@dataclass(frozen=True)
class ToolAction:
    """Par ferramenta/ação autorizado. `action` nulo significa ferramenta sem parâmetro de ação."""

    tool: str
    action: str | None = None
    verified: bool = False

    def __post_init__(self) -> None:
        if is_write_like(self.tool) or (self.action and is_write_like(self.action)):
            msg = f"par com semântica de escrita não pode entrar na allowlist: {self}"
            raise ValueError(msg)

    def __str__(self) -> str:
        return f"{self.tool}:{self.action}" if self.action else self.tool


@dataclass(frozen=True)
class OperationSpec:
    """Pares candidatos de uma operação, em ordem de preferência."""

    operation: Operation
    candidates: tuple[ToolAction, ...]
    release: str = "v0.1"
    required_properties: tuple[str, ...] = ()
    note: str | None = None
    attributes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_verified(self) -> bool:
        return any(candidate.verified for candidate in self.candidates)


READ_ALLOWLIST: dict[Operation, OperationSpec] = {
    Operation.LIST_PROJECTS: OperationSpec(
        Operation.LIST_PROJECTS,
        (ToolAction("core_list_projects", verified=True),),
    ),
    Operation.LIST_TEAMS: OperationSpec(
        Operation.LIST_TEAMS,
        (
            ToolAction("core_list_project_teams", verified=True),
            ToolAction("core_list_teams"),
        ),
    ),
    Operation.GET_TEAM_SETTINGS: OperationSpec(
        Operation.GET_TEAM_SETTINGS,
        (
            ToolAction("work", "get_team_settings", verified=True),
            ToolAction("work_get_team_settings"),
        ),
    ),
    Operation.LIST_ITERATIONS: OperationSpec(
        Operation.LIST_ITERATIONS,
        (
            ToolAction("work", "list_team_iterations", verified=True),
            ToolAction("work", "list_iterations", verified=True),
            ToolAction("work_list_team_iterations"),
        ),
        note="a iteração da equipe traz id e datas; o id é exigido por capacidade e itens",
    ),
    Operation.GET_TEAM_CAPACITY: OperationSpec(
        Operation.GET_TEAM_CAPACITY,
        (
            ToolAction("work", "get_team_capacity", verified=True),
            ToolAction("work_get_team_capacity"),
        ),
        required_properties=("iterationId",),
    ),
    Operation.GET_ITERATION_CAPACITIES: OperationSpec(
        Operation.GET_ITERATION_CAPACITIES,
        (
            ToolAction("work", "get_iteration_capacities", verified=True),
            ToolAction("work_get_iteration_capacities"),
        ),
        required_properties=("iterationId",),
    ),
    Operation.LIST_ITERATION_WORK_ITEMS: OperationSpec(
        Operation.LIST_ITERATION_WORK_ITEMS,
        (
            ToolAction("wit_work_item", "list_for_iteration", verified=True),
            ToolAction("wit_list_work_items_for_iteration"),
        ),
        required_properties=("iterationId",),
    ),
    Operation.GET_WORK_ITEMS_BATCH: OperationSpec(
        Operation.GET_WORK_ITEMS_BATCH,
        (
            ToolAction("wit_work_item", "get_batch", verified=True),
            ToolAction("wit_get_work_items_batch"),
        ),
        required_properties=("ids",),
    ),
    Operation.GET_WORK_ITEM_TYPE: OperationSpec(
        Operation.GET_WORK_ITEM_TYPE,
        (
            ToolAction("wit_work_item", "get_type", verified=True),
            ToolAction("wit_get_work_item_type"),
        ),
    ),
    Operation.LIST_WORK_ITEM_REVISIONS: OperationSpec(
        Operation.LIST_WORK_ITEM_REVISIONS,
        (
            ToolAction("wit_work_item", "list_revisions", verified=True),
            ToolAction("wit_list_work_item_revisions"),
        ),
        required_properties=("workItemId",),
        release="v0.2",
        note="histórico depende de cobertura demonstrada por item (T17)",
    ),
    Operation.GET_QUERY_RESULTS: OperationSpec(
        Operation.GET_QUERY_RESULTS,
        (
            ToolAction("wit_query", "get_results", verified=True),
            ToolAction("wit_get_query_results_by_id"),
        ),
        release="v0.2",
        note="semântica de ASOF precisa ser demonstrada antes do uso histórico",
    ),
}
