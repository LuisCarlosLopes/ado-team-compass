"""Transporte do servidor MCP oficial da Microsoft (remoto por padrão, stdio alternativo).

Conforme a orientação oficial, o canal padrão é o servidor remoto
`https://mcp.azuredevops.com/{organização}/mcp`. A autenticação é a suportada por esse
servidor: o produto não recebe PAT nem token do Azure DevOps e não abre um segundo acesso.
Falha de autenticação vira diagnóstico acionável, nunca conexão alternativa.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from types import TracebackType
from typing import Any, Self, TextIO

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
        errlog: TextIO | None = None,
    ) -> None:
        self._connection = connection
        self._timeout = timeout_seconds
        self._errlog: TextIO = errlog or sys.stderr
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

        parameters = StdioServerParameters(
            command=server.command[0],
            args=list(server.command[1:]),
            env=_host_environment(server.env_ref),
        )

        @asynccontextmanager
        async def stdio_streams() -> Any:
            # O servidor oficial registra diagnóstico no próprio stderr; ele é encaminhado
            # para o destino configurado, sem se misturar à saída JSON do produto.
            async with stdio_client(parameters, errlog=self._errlog) as streams:
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
            declared = schema.get("properties") or {}
            properties = tuple(sorted(declared.keys()))
            action_parameter, actions = _actions_of(declared)
            tools.append(
                ToolDescriptor(
                    name=tool.name,
                    title=getattr(tool, "title", None),
                    description=getattr(tool, "description", None),
                    input_schema_hash=schema_hash(schema),
                    input_properties=properties,
                    action_parameter=action_parameter,
                    actions=actions,
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
        payload, marked = _structured_payload(result)
        if getattr(result, "isError", False):
            return ToolCallResult(
                tool=name,
                is_error=True,
                error_text=_error_text(result),
                payload=payload,
                marked_untrusted=marked,
            )
        return ToolCallResult(tool=name, payload=payload, marked_untrusted=marked)

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


def _actions_of(properties: Mapping[str, Any]) -> tuple[str | None, tuple[str, ...]]:
    """Descobre o parâmetro de ação e os valores aceitos, quando a ferramenta é consolidada."""
    for name in ("action", "operation", "op"):
        specification = properties.get(name)
        if not isinstance(specification, Mapping):
            continue
        values = specification.get("enum")
        if isinstance(values, list) and values:
            return name, tuple(str(value) for value in values)
    return None, ()


def _host_environment(env_ref: str | None) -> dict[str, str] | None:
    """Ambiente do processo do servidor MCP, lido do host na hora da conexão.

    A credencial da sessão pertence à configuração de MCP do host. Ela nunca é copiada para a
    configuração do produto, para artefatos de execução ou para logs.
    """
    if env_ref is None:
        return None
    raw_path, _, server_name = env_ref.partition("#")
    path = Path(raw_path).expanduser()
    if not path.is_file():
        raise ConfigError(
            "E_MCP_ENV_REF_AUSENTE",
            f"A configuração de MCP do host não foi encontrada: {path}.",
            detail={"env_ref": env_ref},
            remediation="Corrija 'env_ref' na conexão ou aponte para o arquivo correto.",
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ConfigError(
            "E_MCP_ENV_REF_INVALIDO",
            f"A configuração de MCP do host em {path} não é JSON válido.",
            detail={"env_ref": env_ref},
        ) from error

    servers = document.get("mcpServers") or document.get("servers") or {}
    entry = servers.get(server_name) if isinstance(servers, dict) else None
    if not isinstance(entry, dict):
        raise ConfigError(
            "E_MCP_ENV_REF_SERVIDOR",
            f"O servidor {server_name!r} não existe na configuração de MCP do host.",
            detail={
                "env_ref": env_ref,
                "available": sorted(servers) if isinstance(servers, dict) else [],
            },
        )
    environment = entry.get("env")
    if not isinstance(environment, dict):
        return None

    from mcp.client.stdio import get_default_environment

    merged = dict(get_default_environment())
    merged.update({str(key): str(value) for key, value in environment.items()})
    return merged


#: O servidor oficial envolve o conteúdo do Azure DevOps em delimitadores de conteúdo não
#: confiável. O produto remove o envelope para ler os dados e registra que ele existia.
_UNTRUSTED_OPEN = re.compile(r"\A<<(?P<token>[0-9a-f]{8,})>>[^\n]*<<(?P=token)>>\n", re.IGNORECASE)


def _unwrap_untrusted(text: str) -> tuple[str, bool]:
    """Remove o envelope de conteúdo não confiável, preservando o corpo exatamente como veio."""
    match = _UNTRUSTED_OPEN.match(text)
    if match is None:
        return text, False
    body = text[match.end() :]
    closing = f"<</{match.group('token')}>>"
    index = body.rfind(closing)
    if index != -1:
        body = body[:index]
    return body.strip(), True


def _structured_payload(result: Any) -> tuple[Any, bool]:
    """Interpreta a resposta em blocos do servidor oficial.

    O servidor devolve o contexto da chamada em um bloco de texto e os dados em outro, cada um
    com seu próprio envelope de conteúdo não confiável. Aqui cada bloco é desembrulhado
    separadamente: os blocos JSON viram os dados e os de texto ficam apenas como contexto.
    O conteúdo continua sendo dado: nada nele altera instruções, comandos ou destinos.
    """
    structured = getattr(result, "structuredContent", None)
    if structured:
        return structured, False

    parsed: list[Any] = []
    texts: list[str] = []
    marked_any = False
    for block in getattr(result, "content", None) or ():
        text = getattr(block, "text", None)
        if text is None:
            continue
        body, marked = _unwrap_untrusted(text)
        marked_any = marked_any or marked
        try:
            parsed.append(json.loads(body))
        except (json.JSONDecodeError, TypeError):
            texts.append(body)

    if not parsed:
        return ("\n".join(texts) or None), marked_any
    if len(parsed) == 1:
        return parsed[0], marked_any
    if all(isinstance(entry, list) for entry in parsed):
        return [item for entry in parsed for item in entry], marked_any
    return parsed[-1], marked_any


def _error_text(result: Any) -> str:
    payload, _ = _structured_payload(result)
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, default=str)


@contextmanager
def official_transport(
    connection: ConnectionConfig,
    *,
    timeout_seconds: float = 30.0,
    errlog_path: Path | None = None,
) -> Iterator[OfficialMcpTransport]:
    """Abre e fecha a sessão com o servidor MCP oficial."""
    handle: TextIO | None = None
    if errlog_path is not None:
        errlog_path.parent.mkdir(parents=True, exist_ok=True)
        handle = errlog_path.open("a", encoding="utf-8")
    try:
        transport = OfficialMcpTransport(connection, timeout_seconds=timeout_seconds, errlog=handle)
        with transport:
            yield transport
    finally:
        if handle is not None:
            handle.close()
