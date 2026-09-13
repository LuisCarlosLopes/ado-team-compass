"""Cliente de leitura sobre o MCP oficial: allowlist, retentativas e registro auditável.

Garantias deste módulo:

- negativa por padrão: só operações da allowlist, resolvidas no catálogo conectado;
- ferramenta com aparência de escrita é recusada mesmo se estiver no catálogo;
- mudança de schema da ferramenta interrompe a coleta com erro de versão;
- retentativas têm orçamento de tempo, respeitam `Retry-After` e nunca trocam de canal;
- cada chamada registra ferramenta, argumentos sanitizados, tentativas e hash do payload.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ado_team_compass.adapters.ado_mcp.allowlist import (
    READ_ALLOWLIST,
    Operation,
    OperationSpec,
    is_write_like,
)
from ado_team_compass.adapters.ado_mcp.catalog import CatalogInfo, negotiate
from ado_team_compass.errors import (
    AccessError,
    CapabilityUnavailable,
    CollectError,
    CompassError,
    SchemaVersionError,
    sanitize_detail,
)
from ado_team_compass.mcp.session.transport import McpTransport, ToolCallResult

__all__ = ["MAX_CONCURRENCY", "AdoMcpClient", "CallRecord", "RetryPolicy"]

#: Concorrência inicial máxima de chamadas ao servidor MCP (plano 5.11).
MAX_CONCURRENCY = 4

_AUTH_HINTS = ("401", "unauthorized", "invalid_token", "authentication", "consent")
_PERMISSION_HINTS = ("403", "forbidden", "access denied", "not authorized")
_THROTTLE_HINTS = ("429", "rate limit", "too many requests", "throttl")
#: O servidor responde com erro quando a equipe não tem capacidade atribuída. Isso é uma
#: configuração ausente da equipe, não uma falha de transporte, e não deve ser retentado.
_NOT_CONFIGURED_HINTS = ("no team capacity", "not assigned to the team", "no capacity assigned")
_TIMEOUT_HINTS = ("timeout", "timed out", "deadline")
_RETRY_AFTER = re.compile(r"retry[-_ ]?after[\"':= ]+(\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class RetryPolicy:
    """Orçamento de retentativa. Esgotado o orçamento, a falha é reportada."""

    max_attempts: int = 3
    budget_seconds: float = 20.0
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 5.0


@dataclass(frozen=True)
class CallRecord:
    """Registro auditável de uma chamada ao MCP oficial."""

    operation: str
    tool: str
    arguments: Mapping[str, Any]
    attempts: int
    started_at: datetime
    finished_at: datetime
    payload_hash: str
    page: int = 1
    error_code: str | None = None


@dataclass
class AdoMcpClient:
    """Executa operações de leitura pelo MCP oficial, com auditoria e sem fallback."""

    transport: McpTransport
    allowlist: Mapping[Operation, OperationSpec] = field(default_factory=lambda: READ_ALLOWLIST)
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    offline: bool = False
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    sleeper: Callable[[float], None] = field(default=time.sleep)
    jitter: Callable[[], float] = field(default_factory=lambda: random.Random(0).random)
    catalog: CatalogInfo | None = field(default=None, init=False)
    call_log: list[CallRecord] = field(default_factory=list, init=False)

    # -- handshake ---------------------------------------------------------------
    def handshake(self) -> CatalogInfo:
        """Lista o catálogo conectado e resolve as operações permitidas."""
        self._require_online("handshake")
        tools = self.transport.list_tools()
        self.catalog = negotiate(
            tools,
            channel=self.transport.description,
            server_version=self.transport.server_version,
            allowlist=self.allowlist,
        )
        return self.catalog

    def supports(self, operation: Operation) -> bool:
        catalog = self.catalog or self.handshake()
        return catalog.operation(operation) is not None

    # -- chamadas ----------------------------------------------------------------
    def call(
        self,
        operation: Operation,
        arguments: Mapping[str, Any] | None = None,
        *,
        expected_schema_hash: str | None = None,
        page: int = 1,
        expect_structured: bool = True,
    ) -> Any:
        """Executa uma operação de leitura resolvida no catálogo conectado.

        Com `expect_structured`, uma resposta sem dados estruturados é erro de coleta: o
        servidor pode devolver apenas o eco do contexto, e isso nunca pode virar contagem zero.
        """
        self._require_online(operation.value)
        arguments = dict(arguments or {})
        spec = self.allowlist.get(operation)
        if spec is None:
            raise AccessError(
                "E_MCP_OPERACAO_FORA_DA_ALLOWLIST",
                f"A operação {operation.value!r} não está na allowlist de leitura.",
                detail={"operation": operation.value},
                remediation="Adicione a operação à allowlist antes de usá-la.",
            )
        self._reject_write_arguments(operation, arguments)

        catalog = self.catalog or self.handshake()
        resolved = catalog.operation(operation)
        if resolved is None:
            raise CapabilityUnavailable(
                "E_MCP_CAPACIDADE_INDISPONIVEL",
                f"O catálogo conectado não oferece a operação {operation.value!r}.",
                detail={
                    "operation": operation.value,
                    "reason": catalog.reason_for(operation),
                    "catalog_hash": catalog.catalog_hash,
                },
                remediation=(
                    "A análise dependente fica indisponível: nenhuma chamada REST, OData, SDK "
                    "ou CLI do Azure DevOps é usada como alternativa."
                ),
            )
        if is_write_like(resolved.tool) or (
            resolved.action is not None and is_write_like(resolved.action)
        ):
            raise AccessError(
                "E_MCP_ACAO_NAO_AUTORIZADA",
                f"O par {resolved.label!r} tem semântica de escrita e foi recusado.",
                detail={
                    "operation": operation.value,
                    "tool": resolved.tool,
                    "action": resolved.action,
                },
                remediation="Somente leitura é permitida nesta versão.",
            )
        if resolved.action is not None:
            parameter = resolved.action_parameter or "action"
            requested = arguments.get(parameter)
            if requested is not None and requested != resolved.action:
                raise AccessError(
                    "E_MCP_ACAO_NAO_AUTORIZADA",
                    f"A ação {requested!r} não é a autorizada para {operation.value!r}.",
                    detail={
                        "operation": operation.value,
                        "tool": resolved.tool,
                        "authorized_action": resolved.action,
                        "requested_action": requested,
                    },
                    remediation="Cada operação usa somente a ação declarada na allowlist.",
                )
            arguments[parameter] = resolved.action
        if expected_schema_hash is not None and expected_schema_hash != resolved.input_schema_hash:
            raise SchemaVersionError(
                "E_MCP_SCHEMA_INCOMPATIVEL",
                f"O schema da ferramenta {resolved.tool!r} mudou desde a última verificação.",
                detail={
                    "tool": resolved.tool,
                    "expected": expected_schema_hash,
                    "connected": resolved.input_schema_hash,
                },
                remediation="Revalide o catálogo e atualize o mapeamento antes de coletar.",
            )

        payload = self._call_with_retry(operation, resolved.tool, arguments, page=page)
        if expect_structured and isinstance(payload, str):
            raise CollectError(
                "E_MCP_RESPOSTA_NAO_ESTRUTURADA",
                f"A resposta de {operation.value!r} não trouxe dados estruturados.",
                detail={
                    "operation": operation.value,
                    "tool": resolved.label,
                    "excerpt": payload[:160],
                },
                remediation=(
                    "A coleta fica parcial em vez de contar zero; verifique escopo, permissão "
                    "e versão do servidor MCP oficial."
                ),
            )
        return payload

    def paginate(
        self,
        operation: Operation,
        arguments: Mapping[str, Any] | None = None,
        *,
        cursor_argument: str = "continuationToken",
        cursor_field: str = "continuationToken",
        items_fields: tuple[str, ...] = ("value",),
        max_pages: int = 50,
    ) -> Iterator[Any]:
        """Percorre páginas enquanto o servidor devolver cursor; página faltante é erro."""
        payload_arguments = dict(arguments or {})
        seen_cursors: set[str] = set()
        for page in range(1, max_pages + 1):
            payload = self.call(operation, payload_arguments, page=page)
            yield payload
            cursor = _extract(payload, cursor_field)
            if not cursor:
                return
            cursor = str(cursor)
            if cursor in seen_cursors:
                raise CollectError(
                    "E_MCP_PAGINACAO_CIRCULAR",
                    "O servidor MCP repetiu o mesmo cursor de paginação.",
                    detail={"operation": operation.value, "page": page},
                    remediation="Reduza o escopo e colete novamente.",
                )
            seen_cursors.add(cursor)
            payload_arguments[cursor_argument] = cursor
            if items_fields and all(
                _extract(payload, field_name) is None for field_name in items_fields
            ):
                raise CollectError(
                    "E_MCP_PAGINA_INCOMPLETA",
                    "Uma página intermediária não trouxe itens, então a coleta é incompleta.",
                    detail={"operation": operation.value, "page": page},
                    remediation="Repita a coleta; resultado parcial não é tratado como total.",
                )
        raise CollectError(
            "E_MCP_PAGINACAO_EXCEDIDA",
            f"A paginação excedeu {max_pages} páginas sem terminar.",
            detail={"operation": operation.value},
            remediation="Reduza o escopo do período ou da área.",
        )

    # -- internos ----------------------------------------------------------------
    def _require_online(self, operation: str) -> None:
        if self.offline:
            raise CapabilityUnavailable(
                "E_MCP_OFFLINE",
                "O modo offline proíbe qualquer chamada ao servidor MCP oficial.",
                detail={"operation": operation},
                remediation="Use demo, replay ou renderização de uma execução já coletada.",
            )

    def _reject_write_arguments(self, operation: Operation, arguments: Mapping[str, Any]) -> None:
        for key, value in arguments.items():
            if not isinstance(value, str):
                continue
            if key.lower() in ("action", "operation", "op", "method") and is_write_like(value):
                raise AccessError(
                    "E_MCP_ACAO_NAO_AUTORIZADA",
                    f"A ação {value!r} é de escrita e não é permitida.",
                    detail={"operation": operation.value, "argument": key},
                    remediation="Esta versão do produto executa apenas leitura.",
                )

    def _call_with_retry(
        self,
        operation: Operation,
        tool: str,
        arguments: Mapping[str, Any],
        *,
        page: int,
    ) -> Any:
        started_at = self.clock()
        deadline = time.monotonic() + self.retry.budget_seconds
        attempts = 0
        last_error: CompassError | None = None

        while attempts < self.retry.max_attempts:
            attempts += 1
            try:
                result = self.transport.call_tool(tool, arguments)
            except Exception as error:
                translated = _translate_exception(error, operation, tool)
                if not _is_retryable(translated) or time.monotonic() >= deadline:
                    self._record(
                        operation,
                        tool,
                        arguments,
                        attempts,
                        started_at,
                        None,
                        page,
                        translated.code,
                    )
                    raise translated from error
                last_error = translated
            else:
                if not result.is_error:
                    self._record(operation, tool, arguments, attempts, started_at, result, page)
                    return result.payload
                translated = _translate_tool_error(result, operation, tool)
                if not _is_retryable(translated) or time.monotonic() >= deadline:
                    self._record(
                        operation,
                        tool,
                        arguments,
                        attempts,
                        started_at,
                        result,
                        page,
                        translated.code,
                    )
                    raise translated
                last_error = translated

            delay = _delay_for(last_error, attempts, self.retry, self.jitter())
            if time.monotonic() + delay >= deadline:
                break
            self.sleeper(delay)

        failure = last_error or CollectError(
            "E_MCP_FALHA_DESCONHECIDA",
            f"A operação {operation.value!r} falhou sem diagnóstico do servidor.",
        )
        self._record(operation, tool, arguments, attempts, started_at, None, page, failure.code)
        raise failure

    def _record(
        self,
        operation: Operation,
        tool: str,
        arguments: Mapping[str, Any],
        attempts: int,
        started_at: datetime,
        result: ToolCallResult | None,
        page: int,
        error_code: str | None = None,
    ) -> None:
        self.call_log.append(
            CallRecord(
                operation=operation.value,
                tool=tool,
                arguments=sanitize_detail(dict(arguments)),
                attempts=attempts,
                started_at=started_at,
                finished_at=self.clock(),
                payload_hash=_payload_hash(result.payload if result else None),
                page=page,
                error_code=error_code,
            )
        )


def _payload_hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def _extract(payload: Any, field_name: str) -> Any:
    if isinstance(payload, Mapping):
        return payload.get(field_name)
    return None


def _is_retryable(error: CompassError) -> bool:
    return error.code in ("E_MCP_LIMITE", "E_MCP_TIMEOUT", "E_MCP_TRANSPORTE")


def _delay_for(
    error: CompassError | None, attempt: int, policy: RetryPolicy, jitter: float
) -> float:
    retry_after = error.detail.get("retry_after_seconds") if error is not None else None
    if isinstance(retry_after, int | float):
        return float(retry_after)
    backoff = policy.base_delay_seconds * float(2 ** (attempt - 1))
    capped = min(policy.max_delay_seconds, backoff)
    return float(capped * (1 + jitter * 0.1))


def _translate_exception(error: Exception, operation: Operation, tool: str) -> CompassError:
    if isinstance(error, CompassError):
        # Erros já traduzidos (acesso, allowlist, schema) sobem preservados.
        return error
    return _classify(str(error), operation, tool)


def _translate_tool_error(result: ToolCallResult, operation: Operation, tool: str) -> CompassError:
    return _classify(result.error_text or "", operation, tool)


def _classify(text: str, operation: Operation, tool: str) -> CompassError:
    lowered = text.lower()
    detail: dict[str, Any] = {"operation": operation.value, "tool": tool}
    if any(hint in lowered for hint in _AUTH_HINTS):
        return AccessError(
            "E_MCP_AUTENTICACAO",
            "O servidor MCP oficial recusou a chamada por autenticação inválida ou ausente.",
            detail=detail,
            remediation=(
                "Autentique a sessão do servidor MCP oficial conforme a orientação da Microsoft; "
                "o produto não mantém credencial própria do Azure DevOps."
            ),
        )
    if any(hint in lowered for hint in _PERMISSION_HINTS):
        return AccessError(
            "E_MCP_PERMISSAO",
            f"A identidade conectada não tem permissão para {operation.value!r}.",
            detail=detail,
            remediation="Solicite leitura do escopo ou reduza o escopo configurado.",
        )
    if any(hint in lowered for hint in _THROTTLE_HINTS):
        match = _RETRY_AFTER.search(text)
        if match:
            detail["retry_after_seconds"] = int(match.group(1))
        return CollectError(
            "E_MCP_LIMITE",
            "O servidor MCP aplicou limite de taxa à coleta.",
            detail=detail,
            remediation="A coleta aguarda o intervalo indicado e tenta novamente.",
        )
    if any(hint in lowered for hint in _NOT_CONFIGURED_HINTS):
        return CollectError(
            "E_MCP_FONTE_NAO_CONFIGURADA",
            f"A fonte de {operation.value!r} não está configurada nesta equipe.",
            detail={**detail, "server_message": text[:200]},
            remediation=(
                "A métrica dependente fica indisponível com motivo; configure a fonte no Azure "
                "DevOps ou desabilite a capacidade para esta equipe."
            ),
        )
    if any(hint in lowered for hint in _TIMEOUT_HINTS):
        return CollectError(
            "E_MCP_TIMEOUT",
            f"A chamada {operation.value!r} excedeu o tempo limite.",
            detail=detail,
            remediation="Reduza o lote ou o escopo e repita a coleta.",
        )
    return CollectError(
        "E_MCP_TRANSPORTE",
        f"Falha na chamada {operation.value!r} ao servidor MCP oficial.",
        detail={**detail, "reason": text[:200]},
        remediation="Verifique a sessão MCP oficial; nenhum canal alternativo é usado.",
    )
