"""T08 — janela, dias elegíveis e capacidade restante. Cenários V01, V08 e V12.

As expectativas numéricas foram calculadas a partir das regras do plano, não da execução
da implementação: 2026-09-14 a 2026-09-18 é uma semana de segunda a sexta.
"""

from datetime import date, datetime
from decimal import Decimal

import pytest

from ado_team_compass.contracts.common import Quantity
from ado_team_compass.contracts.config import CalendarConfig, CurrentDayPolicy
from ado_team_compass.contracts.facts import CapacityReservation, DayOff
from ado_team_compass.metrics.calendar import (
    day_off_fractions,
    eligible_day_factors,
    reserved_capacity,
    resolve_window,
    working_days,
)

TZ = "America/Sao_Paulo"
SPRINT_START = date(2026, 9, 14)
SPRINT_END_INCLUSIVE = date(2026, 9, 18)
BEFORE_SPRINT = datetime.fromisoformat("2026-09-13T12:00:00-03:00")


def _calendar(**overrides) -> CalendarConfig:
    return CalendarConfig(timezone=TZ, **overrides)


def _window(end_inclusive: bool = True):
    return resolve_window(
        SPRINT_START, SPRINT_END_INCLUSIVE, timezone=TZ, end_inclusive=end_inclusive
    )


def _reservation(value: str = "6", unit: str = "hours", activity: str = "Development"):
    return CapacityReservation(
        person_id="p1",
        team_id="t1",
        activity=activity,
        per_day=Quantity(value=Decimal(value), unit=unit),
    )


def test_inclusive_end_is_normalized_to_exclusive_end():
    window = _window()
    assert window.start.isoformat() == "2026-09-14T00:00:00-03:00"
    assert window.end.isoformat() == "2026-09-19T00:00:00-03:00"
    assert len(working_days(window, _calendar())) == 5


def test_exclusive_end_window_excludes_the_last_day():
    window = _window(end_inclusive=False)
    assert working_days(window, _calendar())[-1] == date(2026, 9, 17)


# V01 — 5 dias úteis, 6 unidades/dia, 1 folga: capacidade 24; feriado no mesmo dia
# da folga não reduz para 18.
def test_v01_single_day_off_gives_24_and_overlapping_holiday_does_not_double_discount():
    window = _window()
    day_off = DayOff(person_id="p1", start=date(2026, 9, 16), end=date(2026, 9, 17), source="cap")

    without_holiday = eligible_day_factors(window, BEFORE_SPRINT, _calendar(), days_off=[day_off])
    assert sum(without_holiday.values()) == Decimal(4)
    assert reserved_capacity([_reservation()], without_holiday) == Quantity(
        value=Decimal(24), unit="hours"
    )

    with_overlapping_holiday = eligible_day_factors(
        window,
        BEFORE_SPRINT,
        _calendar(holidays=(date(2026, 9, 16),)),
        days_off=[day_off],
    )
    assert sum(with_overlapping_holiday.values()) == Decimal(4)
    assert reserved_capacity([_reservation()], with_overlapping_holiday) == Quantity(
        value=Decimal(24), unit="hours"
    )


def test_two_sources_of_the_same_day_off_are_a_union():
    fractions = day_off_fractions(
        [
            DayOff(person_id="p1", start=date(2026, 9, 16), end=date(2026, 9, 17), source="a"),
            DayOff(team_id="t1", start=date(2026, 9, 16), end=date(2026, 9, 17), source="b"),
        ]
    )
    assert fractions == {date(2026, 9, 16): Decimal(1)}


def test_partial_day_off_reduces_only_its_fraction_and_keeps_the_largest():
    fractions = day_off_fractions(
        [
            DayOff(
                person_id="p1",
                start=date(2026, 9, 16),
                end=date(2026, 9, 17),
                fraction=Decimal("0.25"),
                source="a",
            ),
            DayOff(
                person_id="p1",
                start=date(2026, 9, 16),
                end=date(2026, 9, 17),
                fraction=Decimal("0.5"),
                source="b",
            ),
        ]
    )
    assert fractions == {date(2026, 9, 16): Decimal("0.5")}
    factors = eligible_day_factors(
        _window(),
        BEFORE_SPRINT,
        _calendar(),
        days_off=[
            DayOff(
                person_id="p1",
                start=date(2026, 9, 16),
                end=date(2026, 9, 17),
                fraction=Decimal("0.5"),
                source="b",
            )
        ],
    )
    assert sum(factors.values()) == Decimal("4.5")
    assert reserved_capacity([_reservation()], factors).value == Decimal(27)


# V12 — fronteiras de data, timezone e política do dia atual.
def test_v12_current_day_is_excluded_by_default_and_included_on_request():
    window = _window()
    as_of = datetime.fromisoformat("2026-09-16T09:00:00-03:00")
    excluded = eligible_day_factors(window, as_of, _calendar())
    assert sorted(excluded) == [date(2026, 9, 17), date(2026, 9, 18)]
    included = eligible_day_factors(
        window, as_of, _calendar(current_day_policy=CurrentDayPolicy.INCLUDE_FULL)
    )
    assert sorted(included) == [date(2026, 9, 16), date(2026, 9, 17), date(2026, 9, 18)]


def test_v12_utc_instant_resolves_the_local_calendar_date():
    window = _window()
    # 02:00Z ainda é 13/09 em São Paulo: a segunda-feira permanece elegível.
    late_night_utc = datetime.fromisoformat("2026-09-14T02:00:00+00:00")
    factors = eligible_day_factors(window, late_night_utc, _calendar())
    assert min(factors) == date(2026, 9, 14)
    assert len(factors) == 5


def test_v12_instant_after_the_window_leaves_no_eligible_day():
    factors = eligible_day_factors(
        _window(), datetime.fromisoformat("2026-09-19T09:00:00-03:00"), _calendar()
    )
    assert factors == {}


def test_v12_no_intraday_proration_without_configured_schedule():
    window = _window()
    morning = eligible_day_factors(
        window,
        datetime.fromisoformat("2026-09-16T08:00:00-03:00"),
        _calendar(current_day_policy=CurrentDayPolicy.INCLUDE_FULL),
    )
    evening = eligible_day_factors(
        window,
        datetime.fromisoformat("2026-09-16T18:00:00-03:00"),
        _calendar(current_day_policy=CurrentDayPolicy.INCLUDE_FULL),
    )
    assert morning == evening


# V08 — dias e horas sem conversão.
def test_v08_reservations_in_different_units_are_not_aggregated():
    factors = eligible_day_factors(_window(), BEFORE_SPRINT, _calendar())
    with pytest.raises(ValueError, match="unidades incompatíveis"):
        reserved_capacity(
            [_reservation(unit="hours"), _reservation(value="1", unit="days", activity="Design")],
            factors,
        )


def test_activities_in_the_same_unit_are_summed():
    factors = eligible_day_factors(_window(), BEFORE_SPRINT, _calendar())
    total = reserved_capacity(
        [_reservation(value="4"), _reservation(value="2", activity="Testing")], factors
    )
    assert total == Quantity(value=Decimal(30), unit="hours")


def test_missing_daily_capacity_stays_missing_instead_of_zero():
    factors = eligible_day_factors(_window(), BEFORE_SPRINT, _calendar())
    unknown = CapacityReservation(
        person_id="p1", team_id="t1", per_day=Quantity(value=None, unit="hours")
    )
    assert reserved_capacity([unknown], factors).is_missing


def test_absence_of_reservations_is_not_zero_capacity():
    with pytest.raises(ValueError, match="Sem reservas conhecidas"):
        reserved_capacity([], {date(2026, 9, 14): Decimal(1)})


def test_non_working_weekdays_are_ignored():
    window = resolve_window(date(2026, 9, 14), date(2026, 9, 20), timezone=TZ, end_inclusive=True)
    assert len(working_days(window, _calendar())) == 5
    assert len(working_days(window, _calendar(working_days=(0, 1, 2, 3, 4, 5, 6)))) == 7
