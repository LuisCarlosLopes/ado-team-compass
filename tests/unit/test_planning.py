"""T19 — regras de planejamento configuráveis. Cenário V20."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ado_team_compass.contracts.common import Provenance, Quantity
from ado_team_compass.contracts.config import (
    PlanningConfig,
    PlanningRule,
    ProcessConfig,
    ScopeConfig,
    StateCategory,
)
from ado_team_compass.contracts.facts import FactSet, WorkItemFact, WorkItemRelation
from ado_team_compass.demo import demo_team
from ado_team_compass.metrics.planning import (
    DEFAULT_ENABLED,
    RULES,
    enabled_rules,
    evaluate_planning,
)

AS_OF = datetime(2026, 9, 15, 12, tzinfo=UTC)
TODAY = date(2026, 9, 15)
PROVENANCE = Provenance(source="mcp", collected_at=AS_OF)


def _item(item_id: int, **overrides) -> WorkItemFact:
    payload = {
        "id": item_id,
        "organization": "contoso",
        "project_id": "proj-demo",
        "item_type": "Task",
        "state": "Committed",
        "state_category": StateCategory.IN_PROGRESS,
        "provenance": PROVENANCE,
    }
    payload.update(overrides)
    return WorkItemFact(**payload)


def _facts(*items: WorkItemFact, relations=()) -> FactSet:
    return FactSet(as_of=AS_OF, items=items, relations=relations)


def _team(**overrides):
    team = demo_team()
    return team.model_copy(update=overrides) if overrides else team


def _rule_ids(findings) -> list[str]:
    return [finding.rule_id for finding in findings]


def test_default_enabled_rules_match_the_plan():
    assert set(DEFAULT_ENABLED) == {
        "inverted_dates",
        "overdue_open_item",
        "parent_ends_before_children",
        "open_work_in_closed_sprint",
        "missing_required_fields",
    }
    assert not RULES["story_without_task"].default_enabled
    assert not RULES["missing_estimate"].default_enabled
    assert not RULES["area_or_iteration_mismatch"].default_enabled


def test_inverted_dates_is_reported_with_policy_and_action():
    findings = evaluate_planning(
        _facts(_item(1, start_date=date(2026, 9, 20), target_date=date(2026, 9, 18))),
        _team(),
        today=TODAY,
    )
    assert _rule_ids(findings) == ["inverted_dates"]
    finding = findings[0]
    assert finding.rule_version == "1.0"
    assert "Política:" in finding.message
    assert finding.evidence == ("evidence/items/1.json",)
    assert finding.condition_to_confirm


def test_overdue_open_item_respects_tolerance():
    facts = _facts(_item(1, target_date=date(2026, 9, 10)))
    strict = evaluate_planning(facts, _team(), today=TODAY)
    assert "overdue_open_item" in _rule_ids(strict)
    tolerant = evaluate_planning(
        facts,
        _team(),
        today=TODAY,
        rules={"overdue_open_item": PlanningRule(enabled=True, tolerance_days=10)},
    )
    assert "overdue_open_item" not in _rule_ids(tolerant)


def test_closed_item_past_its_target_is_not_flagged():
    findings = evaluate_planning(
        _facts(
            _item(
                1,
                target_date=date(2026, 9, 10),
                state="Done",
                state_category=StateCategory.COMPLETED,
            )
        ),
        _team(),
        today=TODAY,
    )
    assert findings == ()


def test_parent_ending_before_children_is_flagged():
    facts = _facts(
        _item(1, item_type="Product Backlog Item", target_date=date(2026, 9, 18)),
        _item(2, target_date=date(2026, 9, 25)),
        relations=(WorkItemRelation(parent_id=1, child_id=2),),
    )
    findings = evaluate_planning(facts, _team(), today=TODAY)
    assert "parent_ends_before_children" in _rule_ids(findings)
    assert findings[0].item_ids == (1,)


def test_open_item_in_a_closed_iteration_is_flagged_only_when_declared():
    facts = _facts(_item(1, iteration_path="Demo\\Sprint 41"))
    silent = evaluate_planning(facts, _team(), today=TODAY)
    assert "open_work_in_closed_sprint" not in _rule_ids(silent)
    flagged = evaluate_planning(facts, _team(), today=TODAY, closed_iterations=("Demo\\Sprint 41",))
    assert "open_work_in_closed_sprint" in _rule_ids(flagged)


def test_required_fields_come_from_the_policy_not_from_a_guess():
    facts = _facts(_item(1, assigned_to=None))
    silent = evaluate_planning(facts, _team(), today=TODAY)
    assert "missing_required_fields" not in _rule_ids(silent)
    flagged = evaluate_planning(
        facts,
        _team(),
        today=TODAY,
        rules={
            "missing_required_fields": PlanningRule(
                enabled=True, exceptions=("require:assigned_to",)
            )
        },
    )
    assert "missing_required_fields" in _rule_ids(flagged)


# V20 — feature entre áreas e story sem task com regra desativada.
def test_v20_disabled_rules_produce_no_false_finding():
    facts = _facts(
        _item(1, item_type="Product Backlog Item", area_path="Outra\\Area"),
        _item(2, remaining_work=None),
    )
    team = _team(
        scope=ScopeConfig(area_paths=("Demo\\Core",), include_descendants=True),
        process=ProcessConfig(accounting_level="leaf_task"),
    )
    findings = evaluate_planning(facts, team, today=TODAY)
    assert _rule_ids(findings) == []


def test_v20_rules_can_be_enabled_per_profile():
    facts = _facts(_item(1, item_type="Product Backlog Item", area_path="Outra\\Area"))
    team = _team(
        scope=ScopeConfig(area_paths=("Demo\\Core",), include_descendants=True),
        process=ProcessConfig(accounting_level="leaf_task"),
        planning=PlanningConfig(
            rules={
                "story_without_task": PlanningRule(enabled=True, severity="atencao"),
                "area_or_iteration_mismatch": PlanningRule(enabled=True),
            }
        ),
    )
    findings = evaluate_planning(facts, team, today=TODAY)
    assert set(_rule_ids(findings)) == {"story_without_task", "area_or_iteration_mismatch"}
    assert findings[0].severity in ("atencao", "info")


def test_descendant_area_is_within_scope_when_configured():
    facts = _facts(_item(1, area_path="Demo\\Core\\Sub"))
    team = _team(scope=ScopeConfig(area_paths=("Demo\\Core",), include_descendants=True))
    findings = evaluate_planning(
        facts, team, today=TODAY, rules={"area_or_iteration_mismatch": PlanningRule(enabled=True)}
    )
    assert findings == ()


def test_item_exception_silences_only_that_item():
    facts = _facts(
        _item(1, start_date=date(2026, 9, 20), target_date=date(2026, 9, 18)),
        _item(2, start_date=date(2026, 9, 20), target_date=date(2026, 9, 18)),
    )
    findings = evaluate_planning(
        facts,
        _team(),
        today=TODAY,
        rules={"inverted_dates": PlanningRule(enabled=True, exceptions=("1",))},
    )
    assert [finding.item_ids for finding in findings] == [(2,)]


def test_missing_estimate_rule_never_imputes_the_original_estimate():
    facts = _facts(_item(1, original_estimate=Quantity(value=Decimal(40), unit="hours")))
    findings = evaluate_planning(
        facts, _team(), today=TODAY, rules={"missing_estimate": PlanningRule(enabled=True)}
    )
    assert "missing_estimate" in _rule_ids(findings)
    assert "não imputar" in (findings[0].condition_to_confirm or "")


def test_findings_are_ordered_by_rule_then_item():
    facts = _facts(
        _item(2, start_date=date(2026, 9, 20), target_date=date(2026, 9, 18)),
        _item(1, start_date=date(2026, 9, 20), target_date=date(2026, 9, 18)),
        _item(3, target_date=date(2026, 9, 1)),
    )
    findings = evaluate_planning(facts, _team(), today=TODAY)
    # Itens 1 e 2 têm alvo futuro: só o item 3 está vencido.
    assert [(finding.rule_id, finding.item_ids[0]) for finding in findings] == [
        ("inverted_dates", 1),
        ("inverted_dates", 2),
        ("overdue_open_item", 3),
    ]


def test_enabled_rules_reflect_configuration():
    team = _team(
        planning=PlanningConfig(
            rules={
                "inverted_dates": PlanningRule(enabled=False),
                "missing_estimate": PlanningRule(enabled=True),
            }
        )
    )
    active = enabled_rules(team)
    assert "inverted_dates" not in active
    assert "missing_estimate" in active


@pytest.mark.parametrize("rule_id", sorted(RULES))
def test_every_rule_declares_policy_and_suggested_action(rule_id):
    spec = RULES[rule_id]
    assert spec.policy and spec.suggested_action and spec.version
