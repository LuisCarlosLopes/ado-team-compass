"""Adaptador do MCP oficial do Azure DevOps: catálogo, allowlist e chamadas de leitura."""

from ado_team_compass.adapters.ado_mcp.allowlist import (
    READ_ALLOWLIST,
    Operation,
    OperationSpec,
    is_write_like,
)
from ado_team_compass.adapters.ado_mcp.catalog import CatalogInfo, ResolvedOperation, negotiate
from ado_team_compass.adapters.ado_mcp.client import AdoMcpClient, CallRecord, RetryPolicy

__all__ = [
    "READ_ALLOWLIST",
    "AdoMcpClient",
    "CallRecord",
    "CatalogInfo",
    "Operation",
    "OperationSpec",
    "ResolvedOperation",
    "RetryPolicy",
    "is_write_like",
    "negotiate",
]
