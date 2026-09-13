"""T25 — forecast experimental e backtesting. Cenários V23 e V24."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ado_team_compass.metrics.forecast import (
    DEFAULT_ITERATIONS,
    MIN_COMPARABLE_COMPLETIONS,
    MIN_COMPLETE_WEEKS,
    backtest,
    simulate,
)

# 16 semanas com 40 conclusões, incluindo semanas de entrega zero.
SAMPLE = (3, 0, 4, 2, 5, 0, 3, 4, 2, 3, 0, 4, 3, 2, 3, 2)


def test_sample_meets_the_experimental_requirements():
    assert len(SAMPLE) >= MIN_COMPLETE_WEEKS
    assert sum(SAMPLE) >= MIN_COMPARABLE_COMPLETIONS


def test_forecast_publishes_premises_sample_and_seed():
    result = simulate(SAMPLE, 20, iterations=2000)
    assert result.available
    assert result.sample == SAMPLE
    assert result.seed and result.iterations == 2000
    assert any("não uma data garantida" in premise for premise in result.premises)
    assert any("uma única equipe" in premise for premise in result.premises)


def test_percentiles_are_ordered_and_expressed_in_periods():
    result = simulate(SAMPLE, 20, iterations=4000)
    assert result.p50_periods is not None and result.p85_periods is not None
    assert result.p85_periods >= result.p50_periods
    # 20 itens com média ~2,5/semana: a mediana fica na casa de 8 semanas.
    assert 6 <= result.p50_periods <= 12


def test_scenarios_include_a_larger_scope():
    result = simulate(SAMPLE, 20, iterations=2000)
    names = [scenario.name for scenario in result.scenarios]
    assert names == ["escopo informado", "escopo +20%"]
    bigger = result.scenarios[1]
    assert bigger.remaining_items == 24
    assert bigger.p50_periods is not None and result.p50_periods is not None
    assert bigger.p50_periods >= result.p50_periods


# V23 — semanas de throughput zero e amostra insuficiente.
def test_v23_zero_weeks_are_preserved_in_the_sample():
    result = simulate(SAMPLE, 10, iterations=1000)
    assert result.sample.count(0) == 3
    assert result.complete_weeks == len(SAMPLE)
    assert result.total_completions == sum(SAMPLE)


def test_v23_forecast_is_denied_when_weeks_are_insufficient():
    result = simulate(SAMPLE[:5], 10)
    assert not result.available
    assert any(f"{MIN_COMPLETE_WEEKS} semanas completas" in reason for reason in result.reasons)
    assert result.scenarios == ()


def test_v23_forecast_is_denied_when_completions_are_insufficient():
    sparse = tuple([1] * 14)
    result = simulate(sparse, 10)
    assert not result.available
    assert any(f"{MIN_COMPARABLE_COMPLETIONS} conclusões" in reason for reason in result.reasons)


def test_v23_sample_without_any_delivery_denies_the_projection():
    result = simulate((0,) * 20, 5, enforce_requirements=False)
    assert not result.available
    assert any("projeção seria infinita" in reason for reason in result.reasons)


def test_no_remaining_scope_produces_no_projection():
    result = simulate(SAMPLE, 0)
    assert not result.available


# V24 — semente reproduz a distribuição.
def test_v24_same_seed_reproduces_the_distribution():
    first = simulate(SAMPLE, 20, seed=42, iterations=2000)
    second = simulate(SAMPLE, 20, seed=42, iterations=2000)
    assert first.scenarios == second.scenarios


def test_v24_different_seed_may_change_the_draw_but_not_the_contract():
    first = simulate(SAMPLE, 20, seed=1, iterations=2000)
    second = simulate(SAMPLE, 20, seed=2, iterations=2000)
    assert first.p50_periods is not None and second.p50_periods is not None
    assert abs(first.p50_periods - second.p50_periods) <= 2


# V24 — backtesting sem vazamento de futuro.
def test_v24_backtesting_trains_only_on_the_past_of_each_cutoff():
    long_series = SAMPLE * 3
    result = backtest(long_series, horizon_periods=4, iterations=500)
    assert result.evaluated > 0
    assert result.p50_coverage is not None and result.p85_coverage is not None
    assert Decimal(0) <= result.p85_coverage <= Decimal(1)
    assert result.p85_coverage >= result.p50_coverage
    assert any("sem vazamento" in reason for reason in result.reasons)


def test_backtesting_is_reproducible_with_the_same_seed():
    long_series = SAMPLE * 3
    assert backtest(long_series, seed=7, iterations=300) == backtest(
        long_series, seed=7, iterations=300
    )


def test_backtesting_refuses_a_short_series():
    result = backtest(SAMPLE[:5])
    assert result.evaluated == 0
    assert any("curta demais" in reason for reason in result.reasons)


def test_default_iteration_count_is_explicit():
    assert DEFAULT_ITERATIONS == 10_000


@pytest.mark.parametrize("scope", [1, 5, 50])
def test_larger_scope_never_shortens_the_projection(scope):
    small = simulate(SAMPLE, scope, iterations=1500)
    larger = simulate(SAMPLE, scope * 2, iterations=1500)
    assert small.p50_periods is not None and larger.p50_periods is not None
    assert larger.p50_periods >= small.p50_periods
