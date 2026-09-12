"""Contrato do relatório de equipe consumido por Markdown, HTML e resumo."""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field

from ado_team_compass.contracts.common import Quantity, StrictModel, Window
from ado_team_compass.contracts.metrics import Finding, Metric

__all__ = ["PersonRow", "TeamReport"]


class PersonRow(StrictModel):
    """Carga e capacidade conhecidas de uma pessoa na janela, com sua classe."""

    person_id: str
    display_name: str | None = None
    known_load: Quantity
    reserved_capacity: Quantity | None = None
    utilization: Decimal | None = None
    load_class: str = "DADOS_INSUFICIENTES"
    is_lower_bound: bool = False
    items_eligible: int = 0
    items_known: int = 0
    items_missing: int = 0
    reason: str | None = None


class TeamReport(StrictModel):
    """Situação atual de uma equipe: números com referência e limitações explícitas."""

    run_id: str
    team_alias: str
    team_id: str
    project_id: str
    profile: str
    as_of: str
    window: Window | None = None
    iteration_path: str | None = None
    unit: str = "hours"
    metrics: tuple[Metric, ...] = ()
    people: tuple[PersonRow, ...] = ()
    findings: tuple[Finding, ...] = ()
    limitations: tuple[str, ...] = ()
    partial_sources: tuple[str, ...] = ()
    evidence_references: dict[str, str] = Field(default_factory=dict)

    def metric(self, metric_id: str) -> Metric | None:
        return next((metric for metric in self.metrics if metric.id == metric_id), None)
