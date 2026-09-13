"""T14 — meta de desempenho: 2.000 itens e 100 pessoas em até 5 segundos, offline.

O tempo do MCP oficial é medido à parte: aqui só entram normalização, cálculo e renderização.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ado_team_compass.contracts.common import Provenance, Quantity, Window
from ado_team_compass.contracts.config import StateCategory
from ado_team_compass.contracts.facts import (
    CapacityReservation,
    DayOff,
    FactSet,
    Person,
    WorkItemFact,
)
from ado_team_compass.demo import demo_team
from ado_team_compass.metrics.engine import build_team_report
from ado_team_compass.reporting import build_summary, render_html, render_markdown

AS_OF = datetime(2026, 9, 15, 15, 0, tzinfo=UTC)
PROVENANCE = Provenance(source="mcp", tool="get_work_items_batch", collected_at=AS_OF)
ITEMS = 2000
PEOPLE = 100
BUDGET_SECONDS = 5.0


def _facts() -> FactSet:
    people = tuple(
        Person(id=f"person-{index:03d}", teams=("team-demo",)) for index in range(PEOPLE)
    )
    reservations = tuple(
        CapacityReservation(
            person_id=person.id,
            team_id="team-demo",
            activity="Development",
            per_day=Quantity(value=Decimal(6), unit="hours"),
        )
        for person in people
    )
    days_off = (
        DayOff(
            person_id=people[0].id,
            start=AS_OF.date(),
            end=AS_OF.date().replace(day=AS_OF.day + 1),
            source="mcp:capacity",
        ),
    )
    items = tuple(
        WorkItemFact(
            id=1000 + index,
            organization="contoso",
            project_id="proj-demo",
            item_type="Task",
            state="Committed",
            state_category=StateCategory.IN_PROGRESS,
            title=f"Item sintético {index}",
            assigned_to=people[index % PEOPLE].id,
            remaining_work=(
                Quantity(value=Decimal(index % 9), unit="hours") if index % 7 else None
            ),
            blocked=index % 50 == 0,
            provenance=PROVENANCE,
        )
        for index in range(ITEMS)
    )
    return FactSet(
        as_of=AS_OF, people=people, reservations=reservations, days_off=days_off, items=items
    )


@pytest.mark.parametrize("renderer", ["markdown", "html"])
def test_large_fixture_is_processed_within_the_reference_budget(renderer):
    facts = _facts()
    team = demo_team()
    window = Window(
        start=datetime(2026, 9, 14, 3, tzinfo=UTC),
        end=datetime(2026, 9, 19, 3, tzinfo=UTC),
        timezone=team.calendar.timezone,
    )
    started = time.perf_counter()
    report = build_team_report(
        facts, team, run_id="perf", as_of=AS_OF, window=window, iteration_path="Demo\\Sprint 42"
    )
    build_summary(report, limit_bytes=24576)
    if renderer == "markdown":
        rendered = render_markdown(report)
    else:
        rendered = render_html(report, items=facts.items)
    elapsed = time.perf_counter() - started

    assert len(report.people) == PEOPLE
    assert rendered
    assert elapsed < BUDGET_SECONDS, f"{renderer} levou {elapsed:.2f}s (meta {BUDGET_SECONDS}s)"


def test_summary_above_the_limit_is_reduced_and_stays_within_budget():
    facts = _facts()
    team = demo_team()
    started = time.perf_counter()
    report = build_team_report(facts, team, run_id="perf", as_of=AS_OF, window=None)
    summary = build_summary(report, limit_bytes=4096)
    elapsed = time.perf_counter() - started
    assert elapsed < BUDGET_SECONDS
    assert not summary.truncated or summary.truncation_reference
