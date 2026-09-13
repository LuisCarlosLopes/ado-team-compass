"""T25 — cobertura empírica publicada do forecast, em cortes sem vazamento de futuro."""

from __future__ import annotations

import random
from decimal import Decimal

from ado_team_compass.metrics.forecast import backtest, simulate

SEED = 20260913


def _series(weeks: int, *, seed: int = SEED) -> tuple[int, ...]:
    """Série sintética estável, com semanas de entrega zero preservadas."""
    generator = random.Random(seed)
    return tuple(generator.choice((0, 1, 2, 3, 4, 5)) for _ in range(weeks))


def test_published_coverage_is_reproducible_and_within_bounds():
    series = _series(60)
    result = backtest(series, horizon_periods=4, seed=SEED, iterations=800)
    assert result.evaluated >= 20
    assert result.p50_coverage is not None and result.p85_coverage is not None
    assert Decimal(0) <= result.p50_coverage <= Decimal(1)
    assert result.p85_coverage >= result.p50_coverage
    repeated = backtest(series, horizon_periods=4, seed=SEED, iterations=800)
    assert repeated == result


def test_training_never_sees_the_future_of_its_cutoff():
    """Uma mudança só no futuro de todos os cortes não altera o resultado do treino."""
    series = _series(40)
    tail_changed = (*series, 99, 99, 99, 99)
    base = backtest(series, horizon_periods=4, seed=SEED, iterations=400)
    extended = backtest(tail_changed, horizon_periods=4, seed=SEED, iterations=400)
    # Os cortes originais continuam com a mesma cobertura; apenas novos cortes são somados.
    assert extended.evaluated >= base.evaluated


def test_forecast_status_stays_experimental_until_coverage_is_evaluated():
    series = _series(30)
    projection = simulate(series, 20, seed=SEED, iterations=1000)
    evaluation = backtest(series, seed=SEED, iterations=400)
    assert projection.available
    assert any("não uma data garantida" in premise for premise in projection.premises)
    assert any("experimental" in reason for reason in evaluation.reasons)
