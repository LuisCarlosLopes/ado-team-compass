"""Diagnóstico de ambiente, configuração e catálogo MCP (entrada `doctor`).

Nada aqui expõe credencial: a sessão é descrita pelo canal e pela versão anunciada.
Sem MCP conectado, o diagnóstico ainda valida ambiente e configuração e declara
explicitamente que a coleta está indisponível.
"""

from __future__ import annotations

import platform
import sys
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from typing import Any

from ado_team_compass import __version__
from ado_team_compass.adapters.ado_mcp import AdoMcpClient, Operation
from ado_team_compass.adapters.ado_mcp.catalog import CatalogInfo
from ado_team_compass.config.loader import ResolvedConfig
from ado_team_compass.contracts.config import ConnectionConfig
from ado_team_compass.errors import CompassError, ExitCode
from ado_team_compass.mcp.session.official import official_transport
from ado_team_compass.mcp.session.transport import McpTransport

__all__ = ["TransportFactory", "diagnose"]

TransportFactory = Callable[[ConnectionConfig], AbstractContextManager[McpTransport]]


def diagnose(
    resolved: ResolvedConfig | None,
    *,
    offline: bool = False,
    transport_factory: TransportFactory | None = None,
) -> tuple[dict[str, Any], ExitCode]:
    """Produz o relatório de diagnóstico e o código de saída correspondente."""
    report: dict[str, Any] = {
        "engine": {
            "name": "ado-team-compass",
            "version": __version__,
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "access_channel": "mcp-oficial-microsoft",
        "offline": offline,
        "configuration": {"status": "ausente"},
        "connections": [],
        "limitations": [],
    }

    if resolved is None:
        report["limitations"].append(
            "configuração não encontrada: execute 'setup' ou informe --config"
        )
        return report, ExitCode.INVALID_INPUT

    report["configuration"] = _configuration_report(resolved)

    if offline:
        report["limitations"].append(
            "modo offline: coleta indisponível; demo, replay e renderização continuam possíveis"
        )
        return report, ExitCode.PARTIAL_CAPABILITY

    factory = transport_factory or _default_factory
    worst = ExitCode.OK
    for connection in resolved.config.connections:
        entry, exit_code = _connection_report(connection, resolved, factory)
        report["connections"].append(entry)
        worst = max(worst, exit_code, key=int)
    return report, worst


def _configuration_report(resolved: ResolvedConfig) -> dict[str, Any]:
    return {
        "status": "valida",
        "schema_version": str(resolved.config.schema_version),
        "teams": [
            {
                "alias": team.alias,
                "project_id": team.project_id,
                "team_id": team.team_id,
                "profile": team.profile.value,
                "capabilities": [capability.value for capability in team.capabilities],
                "timezone": team.calendar.timezone,
                "allocation_unit": team.allocation.unit,
                "current_day_policy": team.calendar.current_day_policy.value,
            }
            for team in resolved.config.teams
        ],
        "output": {
            "directory": resolved.config.output.directory,
            "retention_days": resolved.config.output.retention_days,
        },
    }


def _connection_report(
    connection: ConnectionConfig,
    resolved: ResolvedConfig,
    factory: TransportFactory,
) -> tuple[dict[str, Any], ExitCode]:
    entry: dict[str, Any] = {
        "alias": connection.alias,
        "organization": connection.organization,
        "transport": connection.server.transport.value,
        "endpoint": connection.server.resolved_url(connection.organization)
        if connection.server.transport.value == "http"
        else " ".join(connection.server.command),
    }
    try:
        with factory(connection) as transport:
            client = AdoMcpClient(transport=transport)
            catalog = client.handshake()
    except CompassError as error:
        entry["status"] = "indisponivel"
        entry["error"] = error.as_dict()
        return entry, error.exit_code

    entry["status"] = "conectado"
    entry.update(_catalog_report(catalog))
    required = _required_operations(resolved)
    missing = sorted(
        operation.value for operation in required if catalog.operation(operation) is None
    )
    entry["missing_required_operations"] = missing
    return entry, ExitCode.PARTIAL_CAPABILITY if missing else ExitCode.OK


def _catalog_report(catalog: CatalogInfo) -> Mapping[str, Any]:
    return {
        "server_version": catalog.server_version,
        "catalog_hash": catalog.catalog_hash,
        "tool_count": len(catalog.tool_names),
        "resolved_operations": {
            operation: resolved.tool for operation, resolved in sorted(catalog.resolved.items())
        },
        "unavailable_operations": dict(sorted(catalog.unavailable.items())),
        "rejected_write_tools": list(catalog.rejected_write_tools),
    }


def _required_operations(resolved: ResolvedConfig) -> tuple[Operation, ...]:
    """Operações necessárias às capacidades habilitadas na configuração."""
    required: set[Operation] = {
        Operation.LIST_TEAMS,
        Operation.LIST_ITERATIONS,
        Operation.LIST_ITERATION_WORK_ITEMS,
        Operation.GET_WORK_ITEMS_BATCH,
    }
    for team in resolved.config.teams:
        if any(capability.value == "allocation" for capability in team.capabilities):
            required.add(Operation.GET_TEAM_CAPACITY)
            required.add(Operation.GET_ITERATION_CAPACITIES)
    return tuple(sorted(required, key=lambda operation: operation.value))


def _default_factory(connection: ConnectionConfig) -> AbstractContextManager[McpTransport]:
    return official_transport(connection)
