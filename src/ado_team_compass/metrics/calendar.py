"""Janela, dias elegíveis e capacidade restante reservada (plano 4.1.4).

Regras implementadas aqui:

- `as_of` é sempre explícito; nenhuma função consulta o relógio do sistema;
- eventos chegam em UTC e as fronteiras de calendário são resolvidas no timezone configurado;
- iterações com fim inclusivo são normalizadas para fim exclusivo;
- folgas de equipe, pessoais e feriados formam união: o mesmo dia nunca é descontado duas vezes;
- unidades são preservadas; dias e horas não são convertidos sem fator explícito.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from ado_team_compass.contracts.common import Quantity, Window
from ado_team_compass.contracts.config import CalendarConfig, CurrentDayPolicy
from ado_team_compass.contracts.facts import CapacityReservation, DayOff

__all__ = [
    "day_off_fractions",
    "eligible_day_factors",
    "reserved_capacity",
    "resolve_window",
    "working_days",
]

_FULL_DAY = Decimal(1)


def resolve_window(
    start: date | datetime,
    end: date | datetime,
    *,
    timezone: str,
    end_inclusive: bool = False,
) -> Window:
    """Constrói a janela com fim exclusivo, resolvendo meia-noite no timezone configurado."""
    zone = ZoneInfo(timezone)
    start_at = _to_zone_start(start, zone)
    end_at = _to_zone_start(end, zone)
    if end_inclusive:
        end_at = end_at + timedelta(days=1)
    return Window(start=start_at, end=end_at, timezone=timezone)


def _to_zone_start(value: date | datetime, zone: ZoneInfo) -> datetime:
    if isinstance(value, datetime):
        aware = value if value.tzinfo else value.replace(tzinfo=UTC)
        return aware.astimezone(zone)
    return datetime.combine(value, time.min, tzinfo=zone)


def _local_date(moment: datetime, timezone: str) -> date:
    aware = moment if moment.tzinfo else moment.replace(tzinfo=UTC)
    return aware.astimezone(ZoneInfo(timezone)).date()


def working_days(window: Window, calendar: CalendarConfig) -> tuple[date, ...]:
    """Dias do calendário dentro da janela (início inclusivo, fim exclusivo) que são úteis."""
    first = window.start.astimezone(ZoneInfo(window.timezone)).date()
    last = window.end.astimezone(ZoneInfo(window.timezone)).date()
    days: list[date] = []
    current = first
    while current < last:
        if current.weekday() in calendar.working_days:
            days.append(current)
        current += timedelta(days=1)
    return tuple(days)


def day_off_fractions(days_off: Iterable[DayOff]) -> dict[date, Decimal]:
    """União das folgas por dia: prevalece a maior fração, sem desconto duplicado.

    Folga sem `fraction` vale o dia inteiro. Intervalos usam fim exclusivo.
    """
    fractions: dict[date, Decimal] = {}
    for day_off in days_off:
        fraction = day_off.fraction if day_off.fraction is not None else _FULL_DAY
        current = day_off.start
        while current < day_off.end:
            previous = fractions.get(current, Decimal(0))
            fractions[current] = max(previous, fraction)
            current += timedelta(days=1)
    return fractions


def eligible_day_factors(
    window: Window,
    as_of: datetime,
    calendar: CalendarConfig,
    *,
    days_off: Iterable[DayOff] = (),
) -> dict[date, Decimal]:
    """Fator disponível por dia restante da janela, entre 0 e 1.

    O dia corrente é excluído por padrão (A06); `include_full` conta o dia inteiro.
    Feriados e folgas entram como união: coincidência não reduz a capacidade duas vezes.
    """
    today = _local_date(as_of, calendar.timezone)
    first_eligible = (
        today
        if calendar.current_day_policy is CurrentDayPolicy.INCLUDE_FULL
        else (today + timedelta(days=1))
    )
    blocked = {*calendar.holidays, *calendar.team_days_off}
    fractions = day_off_fractions(days_off)
    factors: dict[date, Decimal] = {}
    for day in working_days(window, calendar):
        if day < first_eligible:
            continue
        if day in blocked:
            continue
        factor = _FULL_DAY - fractions.get(day, Decimal(0))
        if factor <= 0:
            continue
        factors[day] = factor
    return factors


def reserved_capacity(
    reservations: Iterable[CapacityReservation],
    day_factors: Mapping[date, Decimal],
) -> Quantity:
    """Capacidade restante reservada de uma pessoa, somando atividades na mesma unidade.

    Reserva por equipe não prova disponibilidade pessoal: esta função apenas soma o que foi
    reservado. Unidades diferentes não são agregadas.
    """
    reservations = list(reservations)
    if not reservations:
        msg = "Sem reservas conhecidas não existe capacidade reservada a somar."
        raise ValueError(msg)
    units = {reservation.per_day.unit for reservation in reservations}
    if len(units) > 1:
        msg = f"Reservas em unidades incompatíveis não são agregáveis: {sorted(units)}."
        raise ValueError(msg)
    unit = units.pop()
    if any(reservation.per_day.value is None for reservation in reservations):
        return Quantity(value=None, unit=unit)
    available = sum(day_factors.values(), Decimal(0))
    per_day_total = sum(
        (reservation.per_day.value or Decimal(0) for reservation in reservations), Decimal(0)
    )
    return Quantity(value=per_day_total * available, unit=unit)
