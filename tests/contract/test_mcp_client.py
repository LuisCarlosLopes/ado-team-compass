"""T03 — cliente do MCP oficial: catálogo, allowlist, erros e paginação.

Cobre V11 (autenticação, permissão, paginação incompleta, limite e timeout) e V33
(ferramenta ausente/renomeada, schema incompatível, escrita em ferramenta mista e
ausência de qualquer canal direto ao Azure DevOps).
"""

from datetime import UTC, datetime

import pytest

from ado_team_compass.adapters.ado_mcp import AdoMcpClient, Operation, RetryPolicy
from ado_team_compass.adapters.ado_mcp.allowlist import is_write_like
from ado_team_compass.errors import (
    AccessError,
    CapabilityUnavailable,
    CollectError,
    ExitCode,
    SchemaVersionError,
)
from ado_team_compass.mcp.session import FixtureTransport, ToolDescriptor, catalog_hash
from ado_team_compass.mcp.session.transport import ToolCallResult, schema_hash

#: Catálogo espelhando o servidor oficial 2.10.0: ferramentas consolidadas por ação.
CATALOG: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "core_list_projects": ((), ("stateFilter", "top", "continuationToken")),
    "core_list_project_teams": ((), ("project", "top")),
    "work": (
        (
            "list_iterations",
            "list_team_iterations",
            "get_team_settings",
            "get_team_capacity",
            "get_iteration_capacities",
        ),
        ("action", "project", "team", "iterationId"),
    ),
    "wit_work_item": (
        ("get", "get_batch", "list_revisions", "list_for_iteration", "get_type"),
        ("action", "project", "ids", "workItemId", "team", "iterationId"),
    ),
    "wit_query": (("get", "get_results", "wiql"), ("action", "project", "id", "wiql")),
    # Ferramenta mista: `list` é leitura e `reorder` é escrita na mesma ferramenta.
    "wit_backlog": (("list", "list_work_items", "reorder"), ("action", "project", "team")),
}
READ_TOOLS = tuple(CATALOG)
MIXED_WRITE_TOOLS = ("wit_work_item_write", "work_capacity_write", "repo_create_branch")


def _tool(
    name: str,
    properties: tuple[str, ...] | None = None,
    actions: tuple[str, ...] | None = None,
) -> ToolDescriptor:
    declared_actions, declared_properties = CATALOG.get(name, ((), ("project",)))
    resolved_actions = declared_actions if actions is None else actions
    resolved_properties = declared_properties if properties is None else properties
    schema: dict[str, object] = {
        "properties": {item: {"type": "string"} for item in resolved_properties}
    }
    return ToolDescriptor(
        name=name,
        input_schema_hash=schema_hash(schema),
        input_properties=resolved_properties,
        action_parameter="action" if resolved_actions else None,
        actions=resolved_actions,
    )


def _transport(
    names: tuple[str, ...] = READ_TOOLS + MIXED_WRITE_TOOLS, **responses: object
) -> FixtureTransport:
    """Respostas são chaveadas por ferramenta; use `__` para separar a ação (`work__capacity`)."""
    keyed = {name.replace("__", ":"): value for name, value in responses.items()}
    return FixtureTransport(tools=tuple(_tool(name) for name in names), responses=keyed)


def _client(transport: FixtureTransport, **kwargs) -> AdoMcpClient:
    sleeps: list[float] = []
    client = AdoMcpClient(
        transport=transport,
        clock=lambda: datetime(2026, 9, 12, 10, 0, tzinfo=UTC),
        sleeper=sleeps.append,
        jitter=lambda: 0.0,
        **kwargs,
    )
    client.sleeps = sleeps  # type: ignore[attr-defined]
    return client


# -- handshake e catálogo ----------------------------------------------------------
def test_handshake_resolves_read_operations_and_records_the_catalog():
    transport = _transport()
    catalog = _client(transport).handshake()
    assert catalog.operation(Operation.GET_WORK_ITEMS_BATCH) is not None
    assert catalog.catalog_hash == catalog_hash(transport.tools)
    assert catalog.server_version == "fixture"
    assert catalog.channel.startswith("fixture://")


def test_write_tools_and_mixed_tools_are_reported_and_never_resolved():
    catalog = _client(_transport()).handshake()
    # `wit_backlog` é mista: entra na lista por causa da ação de escrita `reorder`.
    assert set(catalog.rejected_write_tools) == {*MIXED_WRITE_TOOLS, "wit_backlog"}
    resolved_tools = {resolved.tool for resolved in catalog.resolved.values()}
    assert "wit_backlog" not in resolved_tools
    assert not any(is_write_like(tool) for tool in resolved_tools)
    assert not any(
        resolved.action and is_write_like(resolved.action) for resolved in catalog.resolved.values()
    )


def test_read_actions_of_a_mixed_tool_are_never_called_for_write():
    """Autorizar leitura em ferramenta mista nunca autoriza a ação de escrita dela."""
    from ado_team_compass.adapters.ado_mcp.allowlist import ToolAction

    with pytest.raises(ValueError, match="semântica de escrita"):
        ToolAction("wit_backlog", "reorder")


def test_history_operation_is_unavailable_when_the_action_is_not_announced():
    """A ferramenta de itens existe, mas o catálogo não anuncia a ação de revisões."""
    tools = tuple(_tool(name) for name in READ_TOOLS)
    reduced = tuple(
        _tool("wit_work_item", actions=("get", "get_batch", "list_for_iteration"))
        if tool.name == "wit_work_item"
        else tool
        for tool in tools
    )
    catalog = _client(FixtureTransport(tools=reduced)).handshake()
    assert catalog.operation(Operation.LIST_WORK_ITEM_REVISIONS) is None
    reason = catalog.reason_for(Operation.LIST_WORK_ITEM_REVISIONS) or ""
    assert "não aceita a ação 'list_revisions'" in reason
    # A leitura de itens continua disponível na mesma ferramenta.
    assert catalog.operation(Operation.GET_WORK_ITEMS_BATCH) is not None


# V33 — ferramenta renomeada.
def test_v33_renamed_tool_is_resolved_from_the_alternate_candidate():
    """Nome antigo, de versões anteriores do servidor, resolve como candidato não verificado."""
    transport = _transport(names=("work_list_team_iterations",))
    catalog = _client(transport).handshake()
    resolved = catalog.operation(Operation.LIST_ITERATIONS)
    assert resolved is not None
    assert resolved.tool == "work_list_team_iterations"
    assert resolved.action is None
    assert not resolved.verified_name
    assert catalog.unverified_operations == ("list_iterations",)


# V33 — ferramenta ausente.
def test_v33_missing_tool_makes_the_capability_unavailable_without_fallback():
    client = _client(_transport(names=("core_list_projects",)))
    with pytest.raises(CapabilityUnavailable) as error:
        client.call(Operation.GET_TEAM_CAPACITY, {"project": "p1"})
    assert error.value.code == "E_MCP_CAPACIDADE_INDISPONIVEL"
    assert error.value.exit_code == ExitCode.PARTIAL_CAPABILITY
    assert "nenhuma chamada REST" in (error.value.remediation or "")


# V33 — schema incompatível.
def test_v33_schema_change_stops_the_collection_with_version_error():
    transport = _transport(wit_work_item__get_batch={"value": []})
    client = _client(transport)
    with pytest.raises(SchemaVersionError) as error:
        client.call(
            Operation.GET_WORK_ITEMS_BATCH, {"ids": [1]}, expected_schema_hash="sha256:antigo"
        )
    assert error.value.code == "E_MCP_SCHEMA_INCOMPATIVEL"
    assert error.value.exit_code == ExitCode.SCHEMA_INCOMPATIBLE


def test_matching_schema_hash_allows_the_call():
    transport = _transport(wit_work_item__get_batch={"value": [{"id": 1}]})
    client = _client(transport)
    resolved = client.handshake().operation(Operation.GET_WORK_ITEMS_BATCH)
    assert resolved is not None
    payload = client.call(
        Operation.GET_WORK_ITEMS_BATCH,
        {"ids": [1]},
        expected_schema_hash=resolved.input_schema_hash,
    )
    assert payload == {"value": [{"id": 1}]}


# V33 — ação de escrita dentro de ferramenta mista.
def test_v33_write_action_argument_is_refused():
    client = _client(_transport(wit_work_item__get_batch={"value": []}))
    with pytest.raises(AccessError) as error:
        client.call(Operation.GET_WORK_ITEMS_BATCH, {"ids": [1], "action": "update"})
    assert error.value.code == "E_MCP_ACAO_NAO_AUTORIZADA"
    assert error.value.exit_code == ExitCode.ACCESS_DENIED


def test_operation_outside_the_allowlist_is_refused():
    client = _client(_transport(), allowlist={})
    with pytest.raises(AccessError) as error:
        client.call(Operation.LIST_PROJECTS)
    assert error.value.code == "E_MCP_OPERACAO_FORA_DA_ALLOWLIST"


# -- V11: autenticação, permissão, limite, timeout ---------------------------------
def test_v11_authentication_failure_is_actionable_and_not_retried():
    transport = _transport(
        core_list_projects=ToolCallResult(
            tool="core_list_projects", is_error=True, error_text="401 Unauthorized: login required"
        )
    )
    client = _client(transport)
    with pytest.raises(AccessError) as error:
        client.call(Operation.LIST_PROJECTS)
    assert error.value.code == "E_MCP_AUTENTICACAO"
    assert len(transport.calls) == 1
    assert "Microsoft" in (error.value.remediation or "")


def test_v11_permission_failure_names_the_operation():
    transport = _transport(
        work__get_team_capacity=ToolCallResult(
            tool="work", is_error=True, error_text="403 Forbidden"
        )
    )
    with pytest.raises(AccessError) as error:
        _client(transport).call(Operation.GET_TEAM_CAPACITY, {"project": "p1"})
    assert error.value.code == "E_MCP_PERMISSAO"
    assert len(transport.calls) == 1


def test_v11_rate_limit_respects_retry_after_and_then_succeeds():
    transport = _transport(
        core_list_projects=[
            ToolCallResult(
                tool="core_list_projects",
                is_error=True,
                error_text="429 too many requests, Retry-After: 3",
            ),
            {"value": [{"id": "p1"}]},
        ]
    )
    client = _client(transport)
    assert client.call(Operation.LIST_PROJECTS) == {"value": [{"id": "p1"}]}
    assert client.sleeps == [3.0]  # type: ignore[attr-defined]
    assert client.call_log[-1].attempts == 2


def test_v11_timeout_is_retried_within_the_budget_and_then_reported():
    transport = _transport(
        core_list_projects=[
            ToolCallResult(tool="core_list_projects", is_error=True, error_text="request timed out")
        ]
        * 3
    )
    client = _client(transport, retry=RetryPolicy(max_attempts=3, budget_seconds=30))
    with pytest.raises(CollectError) as error:
        client.call(Operation.LIST_PROJECTS)
    assert error.value.code == "E_MCP_TIMEOUT"
    assert error.value.exit_code == ExitCode.COLLECT_FAILED
    assert len(transport.calls) == 3


def test_exhausted_time_budget_stops_before_the_attempt_limit():
    transport = _transport(
        core_list_projects=[
            ToolCallResult(tool="core_list_projects", is_error=True, error_text="timeout")
        ]
        * 5
    )
    client = _client(transport, retry=RetryPolicy(max_attempts=5, budget_seconds=0.0))
    with pytest.raises(CollectError):
        client.call(Operation.LIST_PROJECTS)
    assert len(transport.calls) == 1
    assert client.sleeps == []  # type: ignore[attr-defined]


def test_transport_exception_is_translated_without_leaking_internals():
    transport = _transport(core_list_projects=[RuntimeError("socket reset by peer")] * 3)
    client = _client(transport)
    with pytest.raises(CollectError) as error:
        client.call(Operation.LIST_PROJECTS)
    assert error.value.code == "E_MCP_TRANSPORTE"
    assert "nenhum canal alternativo" in (error.value.remediation or "")


# -- V11: paginação ----------------------------------------------------------------
def test_pagination_follows_the_cursor_until_the_last_page():
    transport = _transport(
        wit_work_item__list_for_iteration=[
            {"value": [{"id": 1}], "continuationToken": "c1"},
            {"value": [{"id": 2}]},
        ]
    )
    client = _client(transport)
    pages = list(client.paginate(Operation.LIST_ITERATION_WORK_ITEMS, {"project": "p1"}))
    assert [page["value"][0]["id"] for page in pages] == [1, 2]
    assert transport.calls[1][1]["continuationToken"] == "c1"


def test_v11_incomplete_intermediate_page_is_never_a_silent_zero():
    transport = _transport(
        wit_work_item__list_for_iteration=[
            {"value": [{"id": 1}], "continuationToken": "c1"},
            {"continuationToken": "c2"},
        ]
    )
    client = _client(transport)
    with pytest.raises(CollectError) as error:
        list(client.paginate(Operation.LIST_ITERATION_WORK_ITEMS, {"project": "p1"}))
    assert error.value.code == "E_MCP_PAGINA_INCOMPLETA"


def test_repeated_cursor_is_detected():
    transport = _transport(
        wit_work_item__list_for_iteration=[
            {"value": [], "continuationToken": "c1"},
            {"value": [], "continuationToken": "c1"},
        ]
    )
    with pytest.raises(CollectError) as error:
        list(_client(transport).paginate(Operation.LIST_ITERATION_WORK_ITEMS))
    assert error.value.code == "E_MCP_PAGINACAO_CIRCULAR"


def test_page_limit_is_enforced():
    transport = _transport(
        wit_work_item__list_for_iteration=[
            {"value": [], "continuationToken": f"c{index}"} for index in range(4)
        ]
    )
    with pytest.raises(CollectError) as error:
        list(_client(transport).paginate(Operation.LIST_ITERATION_WORK_ITEMS, max_pages=3))
    assert error.value.code == "E_MCP_PAGINACAO_EXCEDIDA"


# -- V33: offline e auditoria -------------------------------------------------------
def test_v33_offline_mode_never_touches_the_transport():
    transport = _transport(core_list_projects={"value": []})
    client = _client(transport, offline=True)
    with pytest.raises(CapabilityUnavailable) as error:
        client.call(Operation.LIST_PROJECTS)
    assert error.value.code == "E_MCP_OFFLINE"
    assert transport.calls == []
    with pytest.raises(CapabilityUnavailable):
        client.handshake()


def test_call_log_is_auditable_and_sanitized():
    transport = _transport(wit_work_item__get_batch={"value": [{"id": 1}]})
    client = _client(transport)
    client.call(Operation.GET_WORK_ITEMS_BATCH, {"ids": [1], "session_token": "segredo"})
    record = client.call_log[-1]
    assert record.operation == Operation.GET_WORK_ITEMS_BATCH.value
    assert record.tool == "wit_work_item"
    assert record.arguments["action"] == "get_batch"
    assert record.arguments["session_token"] == "[redigido]"
    assert record.payload_hash.startswith("sha256:")
    assert record.error_code is None
    assert record.attempts == 1


def test_failed_call_is_logged_with_its_error_code():
    transport = _transport(
        core_list_projects=ToolCallResult(
            tool="core_list_projects", is_error=True, error_text="403 forbidden"
        )
    )
    client = _client(transport)
    with pytest.raises(AccessError):
        client.call(Operation.LIST_PROJECTS)
    assert client.call_log[-1].error_code == "E_MCP_PERMISSAO"
