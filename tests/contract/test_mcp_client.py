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
MIXED_WRITE_TOOLS = (
    "wit_update_work_item",
    "work_backlog_reorder_items",
    "repo_create_pull_request",
)


def _tool(name: str, properties: tuple[str, ...] = ("project",)) -> ToolDescriptor:
    return ToolDescriptor(
        name=name,
        input_schema_hash=schema_hash(
            {"properties": {name: {"type": "string"} for name in properties}}
        ),
        input_properties=properties,
    )


def _transport(
    names: tuple[str, ...] = READ_TOOLS + MIXED_WRITE_TOOLS, **responses: object
) -> FixtureTransport:
    return FixtureTransport(tools=tuple(_tool(name) for name in names), responses=dict(responses))


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


def test_write_tools_in_the_catalog_are_reported_and_never_resolved():
    catalog = _client(_transport()).handshake()
    assert set(catalog.rejected_write_tools) == set(MIXED_WRITE_TOOLS)
    resolved_tools = {resolved.tool for resolved in catalog.resolved.values()}
    assert not any(is_write_like(tool) for tool in resolved_tools)


def test_history_operations_are_unavailable_when_the_catalog_lacks_them():
    catalog = _client(_transport()).handshake()
    assert catalog.operation(Operation.LIST_WORK_ITEM_REVISIONS) is None
    assert "candidatos tentados" in (catalog.reason_for(Operation.LIST_WORK_ITEM_REVISIONS) or "")


# V33 — ferramenta renomeada.
def test_v33_renamed_tool_is_resolved_from_the_alternate_candidate():
    transport = _transport(names=("work_list_iterations",))
    catalog = _client(transport).handshake()
    resolved = catalog.operation(Operation.LIST_ITERATIONS)
    assert resolved is not None and resolved.tool == "work_list_iterations"


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
    transport = _transport(wit_get_work_items_batch={"value": []})
    client = _client(transport)
    with pytest.raises(SchemaVersionError) as error:
        client.call(
            Operation.GET_WORK_ITEMS_BATCH, {"ids": [1]}, expected_schema_hash="sha256:antigo"
        )
    assert error.value.code == "E_MCP_SCHEMA_INCOMPATIVEL"
    assert error.value.exit_code == ExitCode.SCHEMA_INCOMPATIBLE


def test_matching_schema_hash_allows_the_call():
    transport = _transport(wit_get_work_items_batch={"value": [{"id": 1}]})
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
    client = _client(_transport(wit_get_work_items_batch={"value": []}))
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
        work_get_team_capacity=ToolCallResult(
            tool="work_get_team_capacity", is_error=True, error_text="403 Forbidden"
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
        wit_list_work_items_for_iteration=[
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
        wit_list_work_items_for_iteration=[
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
        wit_list_work_items_for_iteration=[
            {"value": [], "continuationToken": "c1"},
            {"value": [], "continuationToken": "c1"},
        ]
    )
    with pytest.raises(CollectError) as error:
        list(_client(transport).paginate(Operation.LIST_ITERATION_WORK_ITEMS))
    assert error.value.code == "E_MCP_PAGINACAO_CIRCULAR"


def test_page_limit_is_enforced():
    transport = _transport(
        wit_list_work_items_for_iteration=[
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
    transport = _transport(wit_get_work_items_batch={"value": [{"id": 1}]})
    client = _client(transport)
    client.call(Operation.GET_WORK_ITEMS_BATCH, {"ids": [1], "session_token": "segredo"})
    record = client.call_log[-1]
    assert record.operation == Operation.GET_WORK_ITEMS_BATCH.value
    assert record.tool == "wit_get_work_items_batch"
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
