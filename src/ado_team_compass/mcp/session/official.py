"""Transporte do servidor MCP oficial da Microsoft (remoto por padrão, stdio alternativo).

Conforme a orientação oficial, o canal padrão é o servidor remoto
`https://mcp.azuredevops.com/{organização}/mcp`. A autenticação é a suportada por esse
servidor: o produto não recebe PAT nem token do Azure DevOps e não abre um segundo acesso.
Falha de autenticação vira diagnóstico acionável, nunca conexão alternativa.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import timedelta
from types import TracebackType
from typing import Any, Self

from ado_team_compass.contracts.config import ConnectionConfig, McpTransport
from ado_team_compass.errors import AccessError, CollectError, ConfigError
from ado_team_compass.mcp.session.transport import ToolCallResult, ToolDescriptor, schema_hash

__all__ = ["OfficialMcpTransport", "official_transport"]

_AUTH_HINTS = ("401", "unauthorized", "invalid_token", "consent", "login", "authenticate")
_PERMISSION_HINTS = ("403", "forbidden", "not authorized", "access denied")


class OfficialMcpTransport:
    """Sessão com o servidor MCP oficial, aberta como gerenciador de contexto.

    A sessão assíncrona do SDK é mantida por um portal bloqueante para que o motor
    determinístico permaneça sincrônico e testável.
    """

    def __init__(
        self,
        connection: ConnectionConfig,
        *,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._connection = connection
        self._timeout = timeout_seconds
        self._portal: Any = None
        self._portal_cm: Any = None
        self._session: Any = None
        self._session_cm: Any = None
        self._server_version: str | None = None

    @property
    def description(self) -> str:
        server = self._connection.server
        if server.transport is McpTransport.HTTP:
            return f"https official mcp: {server.resolved_url(self._connection.organization)}"
        return f"stdio official mcp: {' '.join(server.command)}"

    @property
    def server_version(self) -> str | None:
        return self._server_version

    def __enter__(self) -> Self:
        from anyio.from_thread import start_blocking_portal

        self._portal_cm = start_blocking_portal()
        self._portal = self._portal_cm.__enter__()
        try:
            self._session_cm = self._portal.wrap_async_context_manager(self._open_session())
            self._session = self._session_cm.__enter__()
        except BaseException:
            self._portal_cm.__exit__(None, None, None)
            self._portal = self._portal_cm = None
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            if self._session_cm is not None:
                self._session_cm.__exit__(exc_type, exc, traceback)
        finally:
            self._session = self._session_cm = None
            if self._portal_cm is not None:
                self._portal_cm.__exit__(exc_type, exc, traceback)
            self._portal = self._portal_cm = None

    def _open_session(self) -> Any:
        from contextlib import asynccontextmanager

        from mcp.client.session import ClientSession

        timeout = timedelta(seconds=self._timeout)

        @asynccontextmanager
        async def opener() -> Any:
            async with self._open_streams() as streams:
                read, write = streams[0], streams[1]
                async with ClientSession(read, write, read_timeout_seconds=timeout) as session:
                    result = await session.initialize()
                    info = getattr(result, "serverInfo", None)
                    self._server_version = getattr(info, "version", None)
                    yield session

        return opener()

    def _open_streams(self) -> Any:
        from contextlib import asynccontextmanager

        server = self._connection.server

        if server.transport is McpTransport.HTTP:
            from mcp.client.streamable_http import streamablehttp_client

            url = server.resolved_url(self._connection.organization)

            @asynccontextmanager
            async def http_streams() -> Any:
                async with streamablehttp_client(url, timeout=self._timeout) as streams:
                    yield streams

            return http_streams()

        from mcp.client.stdio import StdioServerParameters, stdio_client

        parameters = StdioServerParameters(command=server.command[0], args=list(server.command[1:]))

        @asynccontextmanager
        async def stdio_streams() -> Any:
            async with stdio_client(parameters) as streams:
                yield streams

        return stdio_streams()

    def _require_session(self) -> Any:
        if self._session is None or self._portal is None:
            raise ConfigError(
                "E_MCP_SESSAO_FECHADA",
                "A sessão MCP oficial não está aberta.",
                remediation="Use o transporte como gerenciador de contexto antes de coletar.",
            )
        return self._session

    def list_tools(self) -> tuple[ToolDescriptor, ...]:
        """Catálogo anunciado pela conexão, com hash do schema de cada ferramenta."""
        session = self._require_session()
        try:
            result = self._portal.call(session.list_tools)
        except Exception as error:  # traduzido para erro do produto
            raise self._translate(error, operation="list_tools") from error
        tools: list[ToolDescriptor] = []
        for tool in result.tools:
            schema = getattr(tool, "inputSchema", None) or {}
            properties = tuple(sorted((schema.get("properties") or {}).keys()))
            tools.append(
                ToolDescriptor(
                    name=tool.name,
                    title=getattr(tool, "title", None),
                    description=getattr(tool, "description", None),
                    input_schema_hash=schema_hash(schema),
                    input_properties=properties,
                )
            )
        return tuple(tools)

    def call_tool(self, name: str, arguments: Mapping[str, Any]) -> ToolCallResult:
        """Executa uma ferramenta do catálogo e devolve o conteúdo estruturado."""
        session = self._require_session()
        try:
            result = self._portal.call(session.call_tool, name, dict(arguments))
        except Exception as error:  # traduzido para erro do produto
            raise self._translate(error, operation=name) from error
        payload = _structured_payload(result)
        if getattr(result, "isError", False):
            return ToolCallResult(
                tool=name, is_error=True, error_text=_error_text(result), payload=payload
            )
        return ToolCallResult(tool=name, payload=payload)

    def _translate(self, error: Exception, *, operation: str) -> Exception:
        text = str(error).lower()
        detail = {"operation": operation, "channel": self.description}
        if any(hint in text for hint in _AUTH_HINTS):
            return AccessError(
                "E_MCP_AUTENTICACAO",
                "O servidor MCP oficial recusou a sessão por falta de autenticação válida.",
                detail=detail,
                remediation=(
                    "Autentique a sessão do servidor MCP oficial conforme a orientação da "
                    "Microsoft e execute novamente; o produto não usa credencial própria do ADO."
                ),
            )
        if any(hint in text for hint in _PERMISSION_HINTS):
            return AccessError(
                "E_MCP_PERMISSAO",
                "A identidade conectada não tem permissão para o escopo solicitado.",
                detail=detail,
                remediation="Solicite leitura do projeto/equipe ou reduza o escopo configurado.",
            )
        return CollectError(
            "E_MCP_TRANSPORTE",
            "Falha de transporte na comunicação com o servidor MCP oficial.",
            detail={**detail, "reason": type(error).__name__},
            remediation="Verifique conectividade e a sessão do servidor MCP oficial.",
        )


def _structured_payload(result: Any) -> Any:
    """Prefere conteúdo estruturado; texto JSON é interpretado, texto livre é preservado."""
    structured = getattr(result, "structuredContent", None)
    if structured:
        return structured
    texts: list[str] = []
    for block in getattr(result, "content", None) or ():
        text = getattr(block, "text", None)
        if text is not None:
            texts.append(text)
    if not texts:
        return None
    joined = "\n".join(texts)
    try:
        return json.loads(joined)
    except (json.JSONDecodeError, TypeError):
        return joined


def _error_text(result: Any) -> str:
    payload = _structured_payload(result)
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, default=str)


@contextmanager
def official_transport(
    connection: ConnectionConfig, *, timeout_seconds: float = 30.0
) -> Iterator[OfficialMcpTransport]:
    """Abre e fecha a sessão com o servidor MCP oficial."""
    transport = OfficialMcpTransport(connection, timeout_seconds=timeout_seconds)
    with transport:
        yield transport
