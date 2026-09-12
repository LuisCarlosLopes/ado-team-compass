"""Negociação do catálogo conectado: operação lógica → ferramenta concreta verificada.

Nenhum nome de ferramenta é assumido como constante universal. O handshake registra o que o
servidor anunciou, resolve cada operação por candidato e declara indisponível o que não
existir, sem tentar caminho alternativo ao MCP oficial.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import Field

from ado_team_compass.adapters.ado_mcp.allowlist import (
    READ_ALLOWLIST,
    Operation,
    OperationSpec,
    is_write_like,
)
from ado_team_compass.contracts.common import StrictModel
from ado_team_compass.mcp.session.transport import ToolDescriptor, catalog_hash

__all__ = ["CatalogInfo", "ResolvedOperation", "negotiate"]


class ResolvedOperation(StrictModel):
    """Ferramenta concreta escolhida para uma operação lógica."""

    operation: Operation
    tool: str
    input_schema_hash: str
    verified_name: bool = True


class CatalogInfo(StrictModel):
    """Resultado do handshake: catálogo, hash, operações resolvidas e limitações."""

    channel: str
    server_version: str | None = None
    catalog_hash: str
    tool_names: tuple[str, ...] = ()
    resolved: dict[str, ResolvedOperation] = Field(default_factory=dict)
    unavailable: dict[str, str] = Field(default_factory=dict)
    rejected_write_tools: tuple[str, ...] = ()

    def operation(self, operation: Operation) -> ResolvedOperation | None:
        return self.resolved.get(operation.value)

    def reason_for(self, operation: Operation) -> str | None:
        return self.unavailable.get(operation.value)


def negotiate(
    tools: Sequence[ToolDescriptor],
    *,
    channel: str,
    server_version: str | None = None,
    allowlist: Mapping[Operation, OperationSpec] = READ_ALLOWLIST,
) -> CatalogInfo:
    """Resolve as operações permitidas contra o catálogo anunciado pela conexão."""
    by_name = {tool.name: tool for tool in tools}
    resolved: dict[str, ResolvedOperation] = {}
    unavailable: dict[str, str] = {}

    for operation, spec in allowlist.items():
        chosen: ToolDescriptor | None = None
        for candidate in spec.candidates:
            tool = by_name.get(candidate)
            if tool is None:
                continue
            if is_write_like(tool.name):
                continue
            missing = [
                name for name in spec.required_properties if name not in tool.input_properties
            ]
            if missing:
                unavailable[operation.value] = (
                    f"a ferramenta {tool.name!r} do catálogo conectado não expõe os campos "
                    f"necessários: {', '.join(missing)}"
                )
                continue
            chosen = tool
            break
        if chosen is None:
            unavailable.setdefault(
                operation.value,
                "nenhuma ferramenta de leitura do catálogo conectado atende à operação; "
                f"candidatos tentados: {', '.join(spec.candidates)}",
            )
            continue
        resolved[operation.value] = ResolvedOperation(
            operation=operation,
            tool=chosen.name,
            input_schema_hash=chosen.input_schema_hash,
        )

    rejected = tuple(sorted(name for name in by_name if is_write_like(name)))
    return CatalogInfo(
        channel=channel,
        server_version=server_version,
        catalog_hash=catalog_hash(tools),
        tool_names=tuple(sorted(by_name)),
        resolved=resolved,
        unavailable=unavailable,
        rejected_write_tools=rejected,
    )
