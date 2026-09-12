"""Allowlist por ferramenta e ação, com negativa por padrão (contrato MCP, plano 5.9).

Permitir a listagem de um backlog não autoriza reordená-lo: por isso a autorização é por
operação lógica **e** por ferramenta concreta, e qualquer nome com aparência de escrita é
recusado mesmo que apareça no catálogo conectado.

Os nomes de ferramenta abaixo vêm da documentação oficial consultada e permanecem
**não verificados** até o handshake com o servidor conectado (T03/T04).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

__all__ = ["READ_ALLOWLIST", "WRITE_VERBS", "Operation", "OperationSpec", "is_write_like"]


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


#: Verbos que caracterizam escrita. Uma ferramenta mista que os contenha é recusada.
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
    "run",
    "queue",
    "trigger",
)


@dataclass(frozen=True)
class OperationSpec:
    """Ferramentas candidatas de uma operação e o estado de verificação do nome."""

    operation: Operation
    candidates: tuple[str, ...]
    release: str = "v0.1"
    verified: bool = False
    required_properties: tuple[str, ...] = ()
    note: str | None = None


READ_ALLOWLIST: dict[Operation, OperationSpec] = {
    Operation.LIST_PROJECTS: OperationSpec(
        Operation.LIST_PROJECTS,
        ("core_list_projects", "core_list_project"),
    ),
    Operation.LIST_TEAMS: OperationSpec(
        Operation.LIST_TEAMS,
        ("core_list_project_teams", "core_list_teams"),
    ),
    Operation.GET_TEAM_SETTINGS: OperationSpec(
        Operation.GET_TEAM_SETTINGS,
        ("work_get_team_settings",),
    ),
    Operation.LIST_ITERATIONS: OperationSpec(
        Operation.LIST_ITERATIONS,
        ("work_list_team_iterations", "work_list_iterations"),
    ),
    Operation.GET_TEAM_CAPACITY: OperationSpec(
        Operation.GET_TEAM_CAPACITY,
        ("work_get_team_capacity",),
    ),
    Operation.GET_ITERATION_CAPACITIES: OperationSpec(
        Operation.GET_ITERATION_CAPACITIES,
        ("work_get_iteration_capacities",),
    ),
    Operation.LIST_ITERATION_WORK_ITEMS: OperationSpec(
        Operation.LIST_ITERATION_WORK_ITEMS,
        ("wit_list_work_items_for_iteration", "wit_list_iteration_work_items"),
    ),
    Operation.GET_WORK_ITEMS_BATCH: OperationSpec(
        Operation.GET_WORK_ITEMS_BATCH,
        ("wit_get_work_items_batch",),
    ),
    Operation.GET_WORK_ITEM_TYPE: OperationSpec(
        Operation.GET_WORK_ITEM_TYPE,
        ("wit_get_work_item_type",),
    ),
    Operation.LIST_WORK_ITEM_REVISIONS: OperationSpec(
        Operation.LIST_WORK_ITEM_REVISIONS,
        ("wit_list_work_item_revisions",),
        release="v0.2",
        note="histórico depende de cobertura demonstrada em T17",
    ),
    Operation.GET_QUERY_RESULTS: OperationSpec(
        Operation.GET_QUERY_RESULTS,
        ("wit_get_query_results_by_id",),
        release="v0.2",
        note="semântica de ASOF precisa ser demonstrada antes do uso histórico",
    ),
}


def is_write_like(name: str) -> bool:
    """Indica se o nome de ferramenta ou ação contém verbo de escrita.

    A comparação é por segmento para não recusar leitura por coincidência de substring
    (por exemplo `list_revisions` não contém verbo de escrita).
    """
    segments = {segment for segment in name.lower().replace("-", "_").split("_") if segment}
    return bool(segments & set(WRITE_VERBS))
