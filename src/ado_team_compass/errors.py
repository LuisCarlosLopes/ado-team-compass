"""Códigos de saída e erros com código estável, mensagem acionável e detalhe sanitizado."""

from __future__ import annotations

from enum import IntEnum
from typing import Any

__all__ = [
    "AccessError",
    "CapabilityUnavailable",
    "CollectError",
    "CompassError",
    "ConfigError",
    "ExitCode",
    "PartialResult",
    "SchemaVersionError",
    "extract_compass_error",
    "sanitize_detail",
]

_SECRET_HINTS = (
    "token",
    "secret",
    "password",
    "senha",
    "authorization",
    "cookie",
    "apikey",
    "api_key",
    "credential",
)

# "pat" só é segredo como chave inteira ou sufixo: "path" não deve ser redigido.
_SECRET_EXACT = ("pat", "ado_pat")

_REDACTED = "[redigido]"


class ExitCode(IntEnum):
    """Códigos de saída definidos em 4.1.1 do plano."""

    OK = 0
    INVALID_INPUT = 2
    ACCESS_DENIED = 3
    COLLECT_FAILED = 4
    PARTIAL_CAPABILITY = 5
    SCHEMA_INCOMPATIBLE = 6


def sanitize_detail(detail: dict[str, Any] | None) -> dict[str, Any]:
    """Remove valores de chaves com aparência de segredo, preservando a estrutura."""
    if not detail:
        return {}
    sanitized: dict[str, Any] = {}
    for key, value in detail.items():
        lowered = key.lower()
        is_secret = any(hint in lowered for hint in _SECRET_HINTS) or lowered in _SECRET_EXACT
        if is_secret:
            sanitized[key] = _REDACTED
        elif isinstance(value, dict):
            sanitized[key] = sanitize_detail(value)
        elif isinstance(value, list | tuple):
            sanitized[key] = [
                sanitize_detail(item) if isinstance(item, dict) else item for item in value
            ]
        else:
            sanitized[key] = value
    return sanitized


class CompassError(Exception):
    """Erro base: código estável, mensagem acionável em pt-BR e detalhe sanitizado."""

    exit_code: ExitCode = ExitCode.INVALID_INPUT

    def __init__(
        self,
        code: str,
        message: str,
        *,
        detail: dict[str, Any] | None = None,
        remediation: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = sanitize_detail(detail)
        self.remediation = remediation

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "remediation": self.remediation,
            "detail": self.detail,
            "exit_code": int(self.exit_code),
        }

    def __str__(self) -> str:
        if self.remediation:
            return f"[{self.code}] {self.message} Ação: {self.remediation}"
        return f"[{self.code}] {self.message}"


class ConfigError(CompassError):
    """Entrada ou configuração inválida."""

    exit_code = ExitCode.INVALID_INPUT


class AccessError(CompassError):
    """Autenticação ou permissão insuficiente no escopo principal."""

    exit_code = ExitCode.ACCESS_DENIED


class CollectError(CompassError):
    """Falha de coleta sem relatório utilizável."""

    exit_code = ExitCode.COLLECT_FAILED


class PartialResult(CompassError):
    """Relatório produzido com capacidade solicitada parcial ou indisponível."""

    exit_code = ExitCode.PARTIAL_CAPABILITY


class CapabilityUnavailable(PartialResult):
    """Operação não suportada pelo catálogo MCP conectado: capacidade fica indisponível."""


class SchemaVersionError(CompassError):
    """Schema ou versão incompatível com esta instalação."""

    exit_code = ExitCode.SCHEMA_INCOMPATIBLE


def extract_compass_error(exc: BaseException) -> CompassError | None:
    """Extrai uma instância de CompassError, mesmo se empacotada em ExceptionGroup."""
    if isinstance(exc, CompassError):
        return exc
    if isinstance(exc, BaseExceptionGroup):
        for item in exc.exceptions:
            found = extract_compass_error(item)
            if found is not None:
                return found
    return None
