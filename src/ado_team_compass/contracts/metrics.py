"""Contratos de `metrics.json`, `summary.json` e achados (plano 4.1.3)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field

from ado_team_compass.contracts.common import (
    Coverage,
    MetricStatus,
    QualityCounters,
    Quantity,
    StrictModel,
    Window,
)

__all__ = ["Finding", "Metric", "MetricSet", "Summary"]


class Metric(StrictModel):
    """Valor de métrica com definição versionada, status, cobertura e referências."""

    id: str
    definition_version: str
    status: MetricStatus
    quantity: Quantity | None = None
    ratio: Decimal | None = None
    window: Window | None = None
    coverage: Coverage = Coverage()
    quality: QualityCounters = QualityCounters()
    unavailable_reason: str | None = None
    references: tuple[str, ...] = ()

    def model_post_init(self, _context: object) -> None:
        if self.status in (MetricStatus.UNAVAILABLE, MetricStatus.NOT_APPLICABLE) and not (
            self.unavailable_reason
        ):
            msg = f"A métrica {self.id!r} com status {self.status} exige motivo explícito."
            raise ValueError(msg)


class Finding(StrictModel):
    """Achado determinístico: sempre com evidência e condição a confirmar."""

    id: str
    rule_id: str
    rule_version: str
    severity: str
    message: str
    item_ids: tuple[int, ...] = ()
    evidence: tuple[str, ...] = ()
    condition_to_confirm: str | None = None


class MetricSet(StrictModel):
    run_id: str
    team_id: str
    metrics: tuple[Metric, ...] = ()
    findings: tuple[Finding, ...] = ()


class Summary(StrictModel):
    """Resumo para interpretação; nunca trunca fatos ou métricas de auditoria."""

    run_id: str
    team_id: str
    metrics: tuple[Metric, ...] = ()
    findings: tuple[Finding, ...] = ()
    limitations: tuple[str, ...] = ()
    truncated: bool = False
    truncation_reference: str | None = None
    size_limit_bytes: int = Field(default=24576, ge=1024)
