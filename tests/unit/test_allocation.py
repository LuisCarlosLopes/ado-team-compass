"""T09 — carga conhecida e classes locais. Cenários V02, V03, V07, V09 e fronteiras.

Os totais esperados foram calculados a partir das regras do plano 4.1.4.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from ado_team_compass.contracts.common import Provenance, Quantity
from ado_team_compass.contracts.config import StateCategory, Thresholds
from ado_team_compass.contracts.facts import WorkItemFact, WorkItemRelation
from ado_team_compass.metrics.allocation import (
    Classification,
    LoadClass,
    accountable_items,
    classify_load,
    known_load,
)

PROVENANCE = Provenance(source="mcp", collected_at=datetime.fromisoformat("2026-09-12T10:00:00Z"))


def _item(
    item_id: int,
    *,
    remaining: str | None = None,
    unit: str = "hours",
    original: str | None = None,
    category: StateCategory | None = StateCategory.IN_PROGRESS,
    state: str = "Committed",
    item_type: str = "Task",
) -> WorkItemFact:
    return WorkItemFact(
        id=item_id,
        organization="contoso",
        project_id="p1",
        item_type=item_type,
        state=state,
        state_category=category,
        remaining_work=Quantity(value=Decimal(remaining), unit=unit) if remaining else None,
        original_estimate=Quantity(value=Decimal(original), unit=unit) if original else None,
        provenance=PROVENANCE,
    )


def _hours(value: str) -> Quantity:
    return Quantity(value=Decimal(value), unit="hours")


# V02 — 16 de carga conhecida e duas tasks sem restante.
def test_v02_known_load_is_16_with_two_missing_and_no_low_load_classification():
    load = known_load(
        [_item(1, remaining="10"), _item(2, remaining="6"), _item(3), _item(4)], unit="hours"
    )
    assert load.quantity == _hours("16")
    assert (load.counters.eligible, load.counters.known, load.counters.missing) == (4, 2, 2)
    assert not load.is_complete

    classification = classify_load(load, _hours("40"))
    assert classification.load_class is LoadClass.DADOS_INSUFICIENTES
    assert classification.ratio == Decimal("0.4")
    assert classification.is_lower_bound
    assert "sem trabalho restante" in (classification.reason or "")


# V03 — OriginalEstimate 40 e restante ausente.
def test_v03_original_estimate_never_becomes_remaining_work():
    load = known_load([_item(1, original="40")], unit="hours")
    assert load.quantity.is_missing
    assert load.counters.missing == 1
    assert classify_load(load, _hours("40")).load_class is LoadClass.DADOS_INSUFICIENTES


def test_absence_is_not_zero_even_without_any_known_value():
    load = known_load([_item(1), _item(2)], unit="hours")
    assert load.quantity.value is None


def test_empty_eligible_sample_is_no_recorded_load_not_insufficient_data():
    load = known_load([], unit="hours")
    assert load.counters.eligible == 0
    assert classify_load(load, _hours("40")).load_class is LoadClass.SEM_CARGA_REGISTRADA


def test_negative_remaining_work_is_excluded_with_a_finding():
    load = known_load([_item(1, remaining="8"), _item(2, remaining="-4")], unit="hours")
    assert load.quantity == _hours("8")
    assert load.counters.invalid == 1
    assert [finding.rule_id for finding in load.findings] == ["negative_remaining_work"]


def test_completed_item_with_remaining_work_is_an_inconsistency_outside_open_load():
    load = known_load(
        [
            _item(1, remaining="8"),
            _item(2, remaining="5", category=StateCategory.COMPLETED, state="Done"),
        ],
        unit="hours",
    )
    assert load.quantity == _hours("8")
    assert load.counters.eligible == 1
    assert load.counters.excluded == 1
    assert [finding.rule_id for finding in load.findings] == ["completed_with_remaining_work"]


def test_closed_items_without_remaining_work_are_simply_out_of_scope():
    load = known_load(
        [_item(1, remaining="8"), _item(2, category=StateCategory.COMPLETED, state="Done")],
        unit="hours",
    )
    assert load.counters.eligible == 1
    assert load.findings == ()


def test_unmapped_state_invalidates_the_item_with_a_reason():
    load = known_load([_item(1, remaining="8", category=None, state="Em análise")], unit="hours")
    assert load.quantity.is_missing
    assert load.counters.excluded == 1
    assert [finding.rule_id for finding in load.findings] == ["unmapped_state"]


def test_item_in_another_unit_is_invalid_and_never_converted():
    load = known_load([_item(1, remaining="2", unit="days")], unit="hours")
    assert load.counters.invalid == 1
    assert load.quantity.is_missing


# V09 — pai e tasks filhos estimados.
def test_v09_parent_and_children_are_never_summed_together():
    items = [
        _item(100, remaining="40", item_type="Product Backlog Item"),
        _item(101, remaining="16"),
        _item(102, remaining="16"),
    ]
    relations = [
        WorkItemRelation(parent_id=100, child_id=101),
        WorkItemRelation(parent_id=100, child_id=102),
    ]

    leaf = known_load(items, unit="hours", relations=relations, accounting_level="leaf_task")
    assert leaf.quantity == _hours("32")
    assert leaf.counters.eligible == 2

    requirement = known_load(
        items, unit="hours", relations=relations, accounting_level="requirement"
    )
    assert requirement.quantity == _hours("40")
    assert requirement.counters.eligible == 1


def test_parent_estimated_with_unestimated_children_is_an_explicit_limitation():
    items = [_item(100, remaining="40", item_type="Product Backlog Item"), _item(101)]
    relations = [WorkItemRelation(parent_id=100, child_id=101)]
    leaf = known_load(items, unit="hours", relations=relations, accounting_level="leaf_task")
    assert leaf.quantity.is_missing
    assert leaf.counters.missing == 1
    assert not leaf.is_complete


def test_accounting_level_absent_keeps_every_item():
    items = [_item(100, remaining="40"), _item(101, remaining="16")]
    relations = [WorkItemRelation(parent_id=100, child_id=101)]
    assert len(accountable_items(items, relations)) == 2


# V07 — capacidade zero com carga positiva; zero com zero.
def test_v07_positive_load_without_capacity_has_its_own_class():
    load = known_load([_item(1, remaining="16")], unit="hours")
    classification = classify_load(load, _hours("0"))
    assert classification.load_class is LoadClass.CARGA_SEM_CAPACIDADE
    assert classification.ratio is None


def test_v07_zero_load_and_zero_capacity_produce_no_ratio():
    load = known_load([_item(1, remaining="0")], unit="hours")
    classification = classify_load(load, _hours("0"))
    assert classification.load_class is LoadClass.SEM_CARGA_REGISTRADA
    assert classification.ratio is None


def test_unknown_capacity_blocks_classification_but_keeps_lower_bound_visible():
    load = known_load([_item(1, remaining="16")], unit="hours")
    classification = classify_load(load, Quantity(unit="hours"))
    assert classification.load_class is LoadClass.DADOS_INSUFICIENTES
    assert classification.is_lower_bound


def test_incompatible_units_between_load_and_capacity_are_not_compared():
    load = known_load([_item(1, remaining="16")], unit="hours")
    classification = classify_load(load, Quantity(value=Decimal(5), unit="days"))
    assert classification.load_class is LoadClass.DADOS_INSUFICIENTES
    assert "fator explícito" in (classification.reason or "")


@pytest.mark.parametrize(
    ("load_hours", "expected"),
    [
        ("0", LoadClass.SEM_CARGA_REGISTRADA),
        ("0.01", LoadClass.ABAIXO_DA_FAIXA),
        ("59.99", LoadClass.ABAIXO_DA_FAIXA),
        ("60", LoadClass.DENTRO_DA_FAIXA),
        ("90", LoadClass.DENTRO_DA_FAIXA),
        ("90.01", LoadClass.ATENCAO),
        ("110", LoadClass.ATENCAO),
        ("110.01", LoadClass.ACIMA_DA_FAIXA),
    ],
)
def test_threshold_boundaries_are_explicit(load_hours, expected):
    load = known_load([_item(1, remaining=load_hours)], unit="hours")
    assert classify_load(load, _hours("100")).load_class is expected


def test_custom_thresholds_replace_the_defaults():
    load = known_load([_item(1, remaining="50")], unit="hours")
    strict = Thresholds(
        below_range=Decimal("0.40"), within_range=Decimal("0.45"), attention=Decimal("0.49")
    )
    assert classify_load(load, _hours("100"), thresholds=strict).load_class is (
        LoadClass.ACIMA_DA_FAIXA
    )


def test_overload_demonstrated_by_known_load_survives_incomplete_data():
    load = known_load([_item(1, remaining="150"), _item(2)], unit="hours")
    classification = classify_load(load, _hours("100"))
    assert classification.load_class is LoadClass.ACIMA_DA_FAIXA
    assert classification.is_lower_bound


def test_classification_is_a_pure_value_object():
    assert Classification(LoadClass.DENTRO_DA_FAIXA, Decimal("0.7")).reason is None
