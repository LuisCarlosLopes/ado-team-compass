"""Tipos comuns aos contratos: unidades, status, cobertura, janela e proveniência.

Regras preservadas aqui (plano 4.1.3 e 5):

- ausência, zero, não aplicável e amostra vazia são estados distintos;
- unidades são preservadas e nunca convertidas implicitamente;
- cobertura é `valid / eligible`; denominador desconhecido gera cobertura desconhecida.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "Capability",
    "Coverage",
    "MetricStatus",
    "Provenance",
    "QualityCounters",
    "Quantity",
    "SchemaVersion",
    "StrictModel",
    "Window",
]

SCHEMA_MAJOR = 1


class StrictModel(BaseModel):
    """Modelo base: campos desconhecidos são erro e instâncias são imutáveis."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class SchemaVersion(StrictModel):
    """Versão de contrato no formato `major.minor`."""

    major: int = Field(ge=0)
    minor: int = Field(ge=0)

    @classmethod
    def parse(cls, raw: str) -> Self:
        parts = raw.split(".")
        if len(parts) != 2 or not all(part.isdigit() for part in parts):
            msg = f"Versão de schema inválida: {raw!r}. Use o formato 'major.minor'."
            raise ValueError(msg)
        return cls(major=int(parts[0]), minor=int(parts[1]))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}"


class MetricStatus(StrEnum):
    """Estado de uma métrica calculada."""

    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"


class Capability(StrEnum):
    """Capacidades declaráveis por perfil (arquitetura D03)."""

    CURRENT_STATUS = "current_status"
    ALLOCATION = "allocation"
    COMMITMENT = "commitment"
    FLOW_HISTORY = "flow_history"
    PLANNING = "planning"
    FORECAST = "forecast"


class Quantity(StrictModel):
    """Valor com unidade explícita. `value` nulo representa ausência, nunca zero."""

    value: Decimal | None = None
    unit: str

    @property
    def is_missing(self) -> bool:
        return self.value is None

    def add(self, other: Quantity) -> Quantity:
        """Soma preservando unidade; unidades diferentes não são agregáveis."""
        if self.unit != other.unit:
            msg = (
                "Agregação entre unidades incompatíveis não é permitida: "
                f"{self.unit} e {other.unit}."
            )
            raise ValueError(msg)
        if self.value is None and other.value is None:
            return Quantity(value=None, unit=self.unit)
        left = self.value or Decimal(0)
        right = other.value or Decimal(0)
        return Quantity(value=left + right, unit=self.unit)


class Coverage(StrictModel):
    """Cobertura de campo: `valid / eligible`. Denominador desconhecido → razão nula."""

    eligible: int | None = Field(default=None, ge=0)
    valid: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _validate_bounds(self) -> Self:
        if self.eligible is not None and self.valid > self.eligible:
            msg = "Itens válidos não podem exceder os elegíveis."
            raise ValueError(msg)
        return self

    @property
    def ratio(self) -> Decimal | None:
        if self.eligible is None or self.eligible == 0:
            return None
        return Decimal(self.valid) / Decimal(self.eligible)

    @property
    def is_known(self) -> bool:
        return self.eligible is not None


class QualityCounters(StrictModel):
    """Metadados de qualidade por métrica (plano 4.1.3)."""

    eligible: int | None = Field(default=None, ge=0)
    known: int = Field(default=0, ge=0)
    missing: int = Field(default=0, ge=0)
    invalid: int = Field(default=0, ge=0)
    excluded: int = Field(default=0, ge=0)
    reasons: tuple[str, ...] = ()


class Provenance(StrictModel):
    """Origem de um fato: ferramenta/ação MCP, momento da coleta e referências."""

    source: str
    tool: str | None = None
    action: str | None = None
    collected_at: datetime
    references: tuple[str, ...] = ()


class Window(StrictModel):
    """Janela com início inclusivo e fim exclusivo, resolvida no timezone configurado."""

    start: datetime
    end: datetime
    timezone: str

    @model_validator(mode="after")
    def _validate_order(self) -> Self:
        if self.end <= self.start:
            msg = "A janela exige fim exclusivo posterior ao início."
            raise ValueError(msg)
        return self
