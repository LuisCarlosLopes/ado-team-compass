"""Contrato do relatório de equipe consumido por Markdown, HTML e resumo."""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field

from ado_team_compass.contracts.common import Quantity, StrictModel, Window
from ado_team_compass.contracts.metrics import Finding, Metric

__all__ = ["HistoryBlock", "PersonRow", "SeriesPoint", "TeamReport"]


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


class SeriesPoint(StrictModel):
    """Ponto observado de uma série; período sem entrega permanece com zero."""

    period: str
    value: int


class HistoryBlock(StrictModel):
    """Bloco histórico da v0.2. Sem cobertura demonstrada, tudo fica indisponível."""

    available: bool = False
    baseline_label: str | None = None
    baseline_is_technical: bool | None = None
    baseline_size: int = 0
    say_do: Decimal | None = None
    say_do_numerator: int = 0
    say_do_denominator: int = 0
    carry_over: Decimal | None = None
    scope_entered: tuple[int, ...] = ()
    scope_exited: tuple[int, ...] = ()
    scope_round_trip: tuple[int, ...] = ()
    committed_points: Decimal | None = None
    current_points: Decimal | None = None
    points_changed_item_ids: tuple[int, ...] = ()
    throughput: tuple[SeriesPoint, ...] = ()
    reopened_item_ids: tuple[int, ...] = ()
    cycle_time_p50: Decimal | None = None
    cycle_time_p85: Decimal | None = None
    cycle_time_sample: int = 0
    lead_time_p50: Decimal | None = None
    lead_time_sample: int = 0
    small_sample: bool = False
    aging_unknown_item_ids: tuple[int, ...] = ()
    oldest_aging_days: Decimal | None = None
    reasons: tuple[str, ...] = ()


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
    history: HistoryBlock | None = None
    planning_findings: tuple[Finding, ...] = ()

    def metric(self, metric_id: str) -> Metric | None:
        return next((metric for metric in self.metrics if metric.id == metric_id), None)
