"""Transporte abstrato do MCP oficial e transporte de fixture para testes offline.

O produto nunca fala com o Azure DevOps: ele fala com o servidor MCP oficial. Este módulo
define o contrato mínimo desse canal — listar o catálogo e chamar uma ferramenta — de forma
que o motor possa ser testado sem rede e sem credencial.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from ado_team_compass.contracts.common import StrictModel

__all__ = [
    "FixtureTransport",
    "McpTransport",
    "ToolCallResult",
    "ToolDescriptor",
    "catalog_hash",
    "schema_hash",
]


class ToolDescriptor(StrictModel):
    """Ferramenta anunciada pelo servidor conectado, com hash do schema de entrada."""

    name: str
    title: str | None = None
    description: str | None = None
    input_schema_hash: str
    input_properties: tuple[str, ...] = ()


class ToolCallResult(StrictModel):
    """Resultado estruturado de uma chamada de ferramenta."""

    tool: str
    payload: Any = None
    is_error: bool = False
    error_text: str | None = None


def schema_hash(schema: Mapping[str, Any] | None) -> str:
    """Hash estável do schema de entrada, usado para detectar mudança de contrato."""
    canonical = json.dumps(schema or {}, sort_keys=True, ensure_ascii=False, default=str)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def catalog_hash(tools: Sequence[ToolDescriptor]) -> str:
    """Hash do catálogo conectado: nomes e hashes de schema em ordem estável."""
    canonical = json.dumps(
        [[tool.name, tool.input_schema_hash] for tool in sorted(tools, key=lambda t: t.name)],
        ensure_ascii=False,
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


@runtime_checkable
class McpTransport(Protocol):
    """Canal de comunicação com o servidor MCP oficial."""

    @property
    def description(self) -> str:
        """Identificação legível do canal, sem credenciais."""

    @property
    def server_version(self) -> str | None:
        """Versão anunciada pelo servidor, quando disponível."""

    def list_tools(self) -> tuple[ToolDescriptor, ...]:
        """Catálogo anunciado pela conexão."""

    def call_tool(self, name: str, arguments: Mapping[str, Any]) -> ToolCallResult:
        """Executa uma ferramenta do catálogo."""


@dataclass
class FixtureTransport:
    """Transporte determinístico para testes, demo e replay: nenhuma rede é usada.

    `responses` mapeia nome da ferramenta para uma resposta ou uma sequência de respostas
    consumidas em ordem — o que permite exercitar paginação, limites e falhas.
    """

    tools: tuple[ToolDescriptor, ...] = ()
    responses: Mapping[str, Any] = field(default_factory=dict)
    server_version_value: str | None = "fixture"
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    _cursors: dict[str, int] = field(default_factory=dict, init=False)

    @property
    def description(self) -> str:
        return "fixture://ado-team-compass"

    @property
    def server_version(self) -> str | None:
        return self.server_version_value

    def list_tools(self) -> tuple[ToolDescriptor, ...]:
        return self.tools

    def call_tool(self, name: str, arguments: Mapping[str, Any]) -> ToolCallResult:
        self.calls.append((name, dict(arguments)))
        if name not in self.responses:
            return ToolCallResult(
                tool=name, is_error=True, error_text=f"tool {name} not found in fixture"
            )
        planned = self.responses[name]
        if isinstance(planned, list):
            index = self._cursors.get(name, 0)
            if index >= len(planned):
                msg = f"A fixture da ferramenta {name!r} não prevê mais respostas."
                raise AssertionError(msg)
            self._cursors[name] = index + 1
            planned = planned[index]
        if isinstance(planned, BaseException):
            raise planned
        if isinstance(planned, ToolCallResult):
            return planned
        return ToolCallResult(tool=name, payload=planned)
