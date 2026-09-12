"""T07 — qualidade por métrica: status, cobertura e motivo. Cenários V02 e V10."""

from decimal import Decimal

from ado_team_compass.contracts.common import Capability, MetricStatus, QualityCounters, Quantity
from ado_team_compass.contracts.config import ProcessConfig, ProfileName, TeamConfig
from ado_team_compass.metrics import quality
from ado_team_compass.metrics.quality import METRIC_REQUIREMENTS, assess_metric

CAPACITY_TEAM = TeamConfig(
    alias="plataforma",
    connection="contoso",
    project_id="p1",
    team_id="t1",
    profile=ProfileName.SPRINT_WITH_CAPACITY,
    capabilities=(Capability.CURRENT_STATUS, Capability.ALLOCATION),
    process=ProcessConfig(
        remaining_work_field="Microsoft.VSTS.Scheduling.RemainingWork",
        accounting_level="leaf_task",
    ),
)

KANBAN_TEAM = TeamConfig(
    alias="suporte",
    connection="contoso",
    project_id="p1",
    team_id="t2",
    profile=ProfileName.CONTINUOUS_FLOW,
    capabilities=(Capability.CURRENT_STATUS,),
)


def test_full_coverage_is_available():
    metric = assess_metric(
        "known_remaining_work",
        CAPACITY_TEAM,
        counters=QualityCounters(eligible=3, known=3),
        quantity=Quantity(value=Decimal(24), unit="hours"),
        has_reservations=True,
    )
    assert metric.status is MetricStatus.AVAILABLE
    assert metric.coverage.ratio == 1


# V02 — carga conhecida distinta de itens sem restante.
def test_v02_partial_coverage_keeps_the_value_and_the_missing_count():
    metric = assess_metric(
        "known_remaining_work",
        CAPACITY_TEAM,
        counters=QualityCounters(
            eligible=4, known=2, missing=2, reasons=("itens abertos sem trabalho restante",)
        ),
        quantity=Quantity(value=Decimal(16), unit="hours"),
        has_reservations=True,
    )
    assert metric.status is MetricStatus.PARTIAL
    assert metric.quantity is not None and metric.quantity.value == 16
    assert metric.coverage.ratio == Decimal("0.5")
    assert metric.quality.missing == 2


# V10 — time Kanban sem tasks, horas ou sprints.
def test_v10_team_without_hours_gets_not_applicable_without_hygiene_blame():
    metric = assess_metric(
        "known_remaining_work",
        KANBAN_TEAM,
        counters=QualityCounters(eligible=12, known=0, missing=12),
    )
    assert metric.status is MetricStatus.NOT_APPLICABLE
    assert metric.unavailable_reason is not None
    assert "não habilitada" in metric.unavailable_reason
    # Não aplicável não reporta cobertura nem sugere falha de higiene.
    assert metric.coverage.eligible is None
    assert metric.quantity is None


def test_v10_current_status_still_works_for_a_flow_team():
    metric = assess_metric(
        "open_items_count",
        KANBAN_TEAM,
        counters=QualityCounters(eligible=12, known=12),
        quantity=Quantity(value=Decimal(12), unit="items"),
    )
    assert metric.status is MetricStatus.AVAILABLE


def test_missing_process_field_makes_the_metric_not_applicable_with_the_field_name():
    team = CAPACITY_TEAM.model_copy(update={"process": ProcessConfig()})
    metric = assess_metric(
        "known_remaining_work", team, counters=QualityCounters(eligible=4, known=0)
    )
    assert metric.status is MetricStatus.NOT_APPLICABLE
    assert "remaining_work_field" in (metric.unavailable_reason or "")


def test_metric_requiring_reservations_is_not_applicable_without_them():
    metric = assess_metric(
        "reserved_remaining_capacity",
        CAPACITY_TEAM,
        counters=QualityCounters(eligible=3, known=3),
        has_reservations=False,
    )
    assert metric.status is MetricStatus.NOT_APPLICABLE
    assert "capacidade reservada" in (metric.unavailable_reason or "")


def test_unknown_denominator_never_becomes_full_coverage():
    metric = assess_metric(
        "known_remaining_work",
        CAPACITY_TEAM,
        counters=QualityCounters(eligible=None, known=2),
        quantity=Quantity(value=Decimal(16), unit="hours"),
        has_reservations=True,
    )
    assert metric.status is MetricStatus.PARTIAL
    assert metric.coverage.ratio is None
    assert not metric.coverage.is_known


def test_no_valid_value_is_unavailable_with_reason_not_zero():
    metric = assess_metric(
        "known_remaining_work",
        CAPACITY_TEAM,
        counters=QualityCounters(eligible=4, known=0, missing=4),
        has_reservations=True,
    )
    assert metric.status is MetricStatus.UNAVAILABLE
    assert metric.quantity is None
    assert metric.unavailable_reason


def test_empty_sample_counts_zero_where_it_makes_sense():
    countable = assess_metric(
        "open_items_count",
        CAPACITY_TEAM,
        counters=QualityCounters(eligible=0, known=0),
        quantity=Quantity(value=Decimal(0), unit="items"),
    )
    assert countable.status is MetricStatus.AVAILABLE
    assert countable.quantity is not None and countable.quantity.value == 0

    non_countable = assess_metric(
        "known_remaining_work",
        CAPACITY_TEAM,
        counters=QualityCounters(eligible=0, known=0),
        has_reservations=True,
    )
    assert non_countable.status is MetricStatus.UNAVAILABLE


def test_reasons_are_deduplicated_and_preserved():
    metric = assess_metric(
        "known_remaining_work",
        CAPACITY_TEAM,
        counters=QualityCounters(eligible=4, known=2, reasons=("motivo",)),
        quantity=Quantity(value=Decimal(16), unit="hours"),
        has_reservations=True,
        extra_reasons=("motivo", "outro"),
    )
    assert metric.quality.reasons == ("motivo", "outro")


def test_no_aggregate_confidence_score_is_exposed():
    assert not [name for name in dir(quality) if "confidence" in name or "score" in name]
    assert all(
        "confidence" not in field for field in METRIC_REQUIREMENTS["observed_utilization"].__dict__
    )
