"""T10 — consolidação entre equipes. Cenários V04, V05, V06 e V08."""

from datetime import date, datetime
from decimal import Decimal

from ado_team_compass.contracts.common import Provenance, Quantity
from ado_team_compass.contracts.config import PersonalAvailability, StateCategory
from ado_team_compass.contracts.facts import CapacityReservation, WorkItemFact
from ado_team_compass.metrics.cross_team import consolidate_person, deduplicate_items

PROVENANCE = Provenance(source="mcp", collected_at=datetime.fromisoformat("2026-09-12T10:00:00Z"))
WEEK = {date(2026, 9, 14 + offset): Decimal(1) for offset in range(5)}
TEAMS = ("t1", "t2")


def _reservation(team_id: str, value: str = "6", unit: str = "hours") -> CapacityReservation:
    return CapacityReservation(
        person_id="p1",
        team_id=team_id,
        activity="Development",
        per_day=Quantity(value=Decimal(value), unit=unit),
    )


def _item(item_id: int, *, remaining: str | None = None, teams: tuple[str, ...] = ("t1",)):
    return WorkItemFact(
        id=item_id,
        organization="contoso",
        project_id="p1",
        item_type="Task",
        state="Committed",
        state_category=StateCategory.IN_PROGRESS,
        assigned_to="p1",
        remaining_work=Quantity(value=Decimal(remaining), unit="hours") if remaining else None,
        team_memberships=teams,
        provenance=PROVENANCE,
    )


def _availability(per_day: str = "6", unit: str = "hours") -> PersonalAvailability:
    return PersonalAvailability(
        person="p1", unit=unit, per_day=Decimal(per_day), source="informado pela pessoa"
    )


# V04 — 6 horas/dia em dois times, disponibilidade pessoal 6, cinco dias.
def test_v04_reservations_60_against_availability_30_point_to_over_reservation():
    consolidation = consolidate_person(
        "p1",
        observed_teams=TEAMS,
        reservations=[_reservation("t1"), _reservation("t2")],
        day_factors_by_team={"t1": WEEK, "t2": WEEK},
        unit="hours",
        personal_availability=_availability(),
    )
    assert consolidation.reserved_total == Quantity(value=Decimal(60), unit="hours")
    assert consolidation.personal_availability == Quantity(value=Decimal(30), unit="hours")
    assert consolidation.is_over_reserved
    assert consolidation.reservations_by_team["t1"].value == Decimal(30)


# V05 — mesmo cenário sem disponibilidade pessoal.
def test_v05_without_personal_availability_global_utilization_is_null():
    consolidation = consolidate_person(
        "p1",
        observed_teams=TEAMS,
        reservations=[_reservation("t1"), _reservation("t2")],
        day_factors_by_team={"t1": WEEK, "t2": WEEK},
        items=[_item(1, remaining="10")],
        unit="hours",
        personal_availability=None,
    )
    assert consolidation.reserved_total.value == Decimal(60)
    assert consolidation.global_utilization is None
    assert consolidation.personal_availability is None
    assert not consolidation.is_over_reserved
    assert any("utilização global nula" in note for note in consolidation.limitations)


def test_summing_reservations_never_becomes_availability():
    consolidation = consolidate_person(
        "p1",
        observed_teams=TEAMS,
        reservations=[_reservation("t1"), _reservation("t2")],
        day_factors_by_team={"t1": WEEK, "t2": WEEK},
        items=[_item(1, remaining="45")],
        unit="hours",
    )
    # 45 / 60 seria 0,75, mas reserva não é disponibilidade: nada é publicado.
    assert consolidation.global_utilization is None


def test_global_utilization_uses_the_declared_availability_in_the_union_of_days():
    consolidation = consolidate_person(
        "p1",
        observed_teams=TEAMS,
        reservations=[_reservation("t1"), _reservation("t2")],
        day_factors_by_team={"t1": WEEK, "t2": WEEK},
        items=[_item(1, remaining="15")],
        unit="hours",
        personal_availability=_availability(),
    )
    assert consolidation.personal_availability is not None
    assert consolidation.personal_availability.value == Decimal(30)
    assert consolidation.global_utilization == Decimal("0.5")


def test_partial_load_marks_the_global_utilization_as_partial():
    consolidation = consolidate_person(
        "p1",
        observed_teams=("t1",),
        reservations=[_reservation("t1")],
        day_factors_by_team={"t1": WEEK},
        items=[_item(1, remaining="15"), _item(2)],
        unit="hours",
        personal_availability=_availability(),
    )
    assert consolidation.global_utilization == Decimal("0.5")
    assert any("parcial" in note for note in consolidation.limitations)


# V06 — mesmo ID retornado por duas áreas/times.
def test_v06_same_item_from_two_teams_is_counted_once_and_overlap_is_shown():
    duplicated = [
        _item(101, remaining="8", teams=("t1",)),
        _item(101, remaining="8", teams=("t2",)),
        _item(102, remaining="4", teams=("t2",)),
    ]
    unique, overlapping = deduplicate_items(duplicated)
    assert len(unique) == 2
    assert overlapping == (101,)
    assert unique[0].team_memberships == ("t1", "t2")

    consolidation = consolidate_person(
        "p1",
        observed_teams=TEAMS,
        reservations=[_reservation("t1")],
        day_factors_by_team={"t1": WEEK, "t2": WEEK},
        items=duplicated,
        unit="hours",
        personal_availability=_availability(),
    )
    assert consolidation.load.quantity == Quantity(value=Decimal(12), unit="hours")
    assert consolidation.overlapping_item_ids == (101,)
    assert any("sobrepostos" in note for note in consolidation.limitations)


def test_items_of_other_people_are_not_consolidated():
    other = _item(200, remaining="8").model_copy(update={"assigned_to": "p2"})
    consolidation = consolidate_person(
        "p1",
        observed_teams=("t1",),
        reservations=[_reservation("t1")],
        day_factors_by_team={"t1": WEEK},
        items=[_item(1, remaining="8"), other],
        unit="hours",
    )
    assert consolidation.load.quantity.value == Decimal(8)
    assert consolidation.load.counters.eligible == 1


# V08 — dias e horas sem conversão.
def test_v08_team_reserving_in_another_unit_is_reported_as_unavailable_aggregation():
    consolidation = consolidate_person(
        "p1",
        observed_teams=TEAMS,
        reservations=[_reservation("t1"), _reservation("t2", value="1", unit="days")],
        day_factors_by_team={"t1": WEEK, "t2": WEEK},
        unit="hours",
        personal_availability=_availability(),
    )
    assert set(consolidation.reservations_by_team) == {"t1"}
    assert consolidation.reserved_total.value == Decimal(30)
    assert any("incompatível" in note for note in consolidation.limitations)


def test_v08_availability_in_another_unit_is_not_converted():
    consolidation = consolidate_person(
        "p1",
        observed_teams=("t1",),
        reservations=[_reservation("t1")],
        day_factors_by_team={"t1": WEEK},
        items=[_item(1, remaining="15")],
        unit="hours",
        personal_availability=_availability(per_day="1", unit="days"),
    )
    assert consolidation.personal_availability is None
    assert consolidation.global_utilization is None


def test_team_without_known_reservation_is_reported_not_assumed():
    consolidation = consolidate_person(
        "p1",
        observed_teams=TEAMS,
        reservations=[_reservation("t1")],
        day_factors_by_team={"t1": WEEK, "t2": WEEK},
        unit="hours",
    )
    assert set(consolidation.reservations_by_team) == {"t1"}
    assert any("não expõe reserva conhecida" in note for note in consolidation.limitations)


def test_observed_universe_is_always_declared():
    consolidation = consolidate_person(
        "p1",
        observed_teams=TEAMS,
        reservations=[_reservation("t1")],
        day_factors_by_team={"t1": WEEK},
        unit="hours",
    )
    assert consolidation.observed_teams == TEAMS
    assert any("universo observado" in note for note in consolidation.limitations)


def test_distinct_windows_per_team_use_the_union_of_eligible_days():
    partial_week = {date(2026, 9, 14): Decimal(1), date(2026, 9, 15): Decimal("0.5")}
    consolidation = consolidate_person(
        "p1",
        observed_teams=TEAMS,
        reservations=[_reservation("t1"), _reservation("t2")],
        day_factors_by_team={"t1": WEEK, "t2": partial_week},
        unit="hours",
        personal_availability=_availability(),
    )
    # União dos dias é a semana inteira: 5 dias * 6 = 30, sem contar duas vezes.
    assert consolidation.personal_availability is not None
    assert consolidation.personal_availability.value == Decimal(30)
    assert consolidation.reservations_by_team["t2"].value == Decimal(9)
