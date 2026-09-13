"""Forecast experimental por simulação de Monte Carlo (plano 4.1.6, T25).

O que este módulo promete: uma distribuição de períodos necessários para concluir um escopo
restante explícito, **dada** a amostra de throughput observada de uma única equipe, com
semente registrada e premissas declaradas.

O que ele não promete: data garantida, comparação de produtividade entre equipes, conversão de
pontos em itens e projeção sem histórico suficiente. Sem os requisitos mínimos, a projeção é
negada com o requisito faltante — o limite é de produto, não garantia estatística.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal

__all__ = [
    "DEFAULT_ITERATIONS",
    "MIN_COMPARABLE_COMPLETIONS",
    "MIN_COMPLETE_WEEKS",
    "Backtest",
    "ForecastResult",
    "ForecastScenario",
    "backtest",
    "simulate",
]

#: Requisitos mínimos experimentais (plano 4.1.6): limite de produto, não garantia estatística.
MIN_COMPLETE_WEEKS = 12
MIN_COMPARABLE_COMPLETIONS = 30
DEFAULT_ITERATIONS = 10_000

_PREMISES = (
    "a amostra de throughput vem de uma única equipe e de itens comparáveis",
    "períodos sem entrega permanecem na amostra e reduzem a projeção",
    "o escopo restante é explícito e não cresce sozinho durante a simulação",
    "o resultado é uma distribuição condicionada ao passado observado, não uma data garantida",
)


@dataclass(frozen=True)
class ForecastScenario:
    """Cenário de escopo com seus percentis, em períodos da amostra."""

    name: str
    remaining_items: int
    p50_periods: int | None
    p85_periods: int | None


@dataclass(frozen=True)
class ForecastResult:
    """Resultado da simulação, sempre com premissas, amostra e semente registradas."""

    available: bool
    sample: tuple[int, ...] = ()
    complete_weeks: int = 0
    total_completions: int = 0
    seed: int = 0
    iterations: int = 0
    scenarios: tuple[ForecastScenario, ...] = ()
    premises: tuple[str, ...] = _PREMISES
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def p50_periods(self) -> int | None:
        return self.scenarios[0].p50_periods if self.scenarios else None

    @property
    def p85_periods(self) -> int | None:
        return self.scenarios[0].p85_periods if self.scenarios else None


def _requirements_report(sample: Sequence[int]) -> tuple[str, ...]:
    reasons: list[str] = []
    if len(sample) < MIN_COMPLETE_WEEKS:
        reasons.append(
            f"requisito faltante: ao menos {MIN_COMPLETE_WEEKS} semanas completas "
            f"(a amostra tem {len(sample)})"
        )
    total = sum(sample)
    if total < MIN_COMPARABLE_COMPLETIONS:
        reasons.append(
            f"requisito faltante: ao menos {MIN_COMPARABLE_COMPLETIONS} conclusões "
            f"comparáveis (a amostra tem {total})"
        )
    return tuple(reasons)


def simulate(
    sample: Sequence[int],
    remaining_items: int,
    *,
    seed: int = 20260913,
    iterations: int = DEFAULT_ITERATIONS,
    scope_scenarios: Mapping[str, int] | None = None,
    enforce_requirements: bool = True,
    max_periods: int = 520,
) -> ForecastResult:
    """Projeta quantos períodos seriam necessários para concluir o escopo restante."""
    sample = tuple(int(value) for value in sample)
    reasons = list(_requirements_report(sample))
    if enforce_requirements and reasons:
        return ForecastResult(
            available=False,
            sample=sample,
            complete_weeks=len(sample),
            total_completions=sum(sample),
            seed=seed,
            reasons=tuple(reasons),
        )
    if not sample or remaining_items <= 0:
        return ForecastResult(
            available=False,
            sample=sample,
            complete_weeks=len(sample),
            total_completions=sum(sample),
            seed=seed,
            reasons=tuple((*reasons, "sem amostra ou sem escopo restante não há projeção a fazer")),
        )
    if all(value == 0 for value in sample):
        return ForecastResult(
            available=False,
            sample=sample,
            complete_weeks=len(sample),
            total_completions=0,
            seed=seed,
            reasons=tuple(
                (
                    *reasons,
                    "a amostra não tem nenhuma conclusão: a projeção seria infinita e é negada",
                )
            ),
        )

    scenarios_input = dict(
        scope_scenarios
        or {
            "escopo informado": remaining_items,
            "escopo +20%": round(remaining_items * 1.2),
        }
    )
    scenarios: list[ForecastScenario] = []
    for name, scope in scenarios_input.items():
        durations = _simulate_scope(
            sample, scope, seed=seed, iterations=iterations, max_periods=max_periods
        )
        scenarios.append(
            ForecastScenario(
                name=name,
                remaining_items=scope,
                p50_periods=_percentile(durations, 50),
                p85_periods=_percentile(durations, 85),
            )
        )
    return ForecastResult(
        available=True,
        sample=sample,
        complete_weeks=len(sample),
        total_completions=sum(sample),
        seed=seed,
        iterations=iterations,
        scenarios=tuple(scenarios),
        reasons=tuple(reasons),
    )


def _simulate_scope(
    sample: Sequence[int],
    remaining_items: int,
    *,
    seed: int,
    iterations: int,
    max_periods: int,
) -> list[int]:
    """Uma trajetória por iteração; a semente torna a distribuição reproduzível."""
    generator = random.Random(seed)
    durations: list[int] = []
    for _ in range(iterations):
        delivered = 0
        periods = 0
        while delivered < remaining_items and periods < max_periods:
            delivered += generator.choice(sample)
            periods += 1
        durations.append(periods)
    return durations


def _percentile(values: Sequence[int], target: int) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, -(-target * len(ordered) // 100))
    return ordered[min(rank, len(ordered)) - 1]


@dataclass(frozen=True)
class Backtest:
    """Avaliação retrospectiva: cobertura empírica de p50 e p85 em cortes sem vazamento."""

    cutoffs: int
    evaluated: int
    p50_coverage: Decimal | None
    p85_coverage: Decimal | None
    seed: int
    reasons: tuple[str, ...] = field(default_factory=tuple)


def backtest(
    series: Sequence[int],
    *,
    horizon_periods: int = 4,
    seed: int = 20260913,
    iterations: int = 2000,
    min_training_periods: int = MIN_COMPLETE_WEEKS,
) -> Backtest:
    """Avalia a projeção em cortes históricos, treinando apenas com o passado de cada corte."""
    series = tuple(int(value) for value in series)
    if len(series) < min_training_periods + horizon_periods:
        return Backtest(
            cutoffs=0,
            evaluated=0,
            p50_coverage=None,
            p85_coverage=None,
            seed=seed,
            reasons=(
                "série curta demais para backtesting: é preciso treino mínimo mais horizonte",
            ),
        )

    within_p50 = 0
    within_p85 = 0
    evaluated = 0
    for cutoff in range(min_training_periods, len(series) - horizon_periods + 1):
        training = series[:cutoff]
        future = series[cutoff : cutoff + horizon_periods]
        observed = sum(future)
        if observed <= 0:
            continue
        result = simulate(
            training,
            observed,
            seed=seed + cutoff,
            iterations=iterations,
            scope_scenarios={"observado": observed},
            enforce_requirements=False,
        )
        if not result.available or result.p50_periods is None or result.p85_periods is None:
            continue
        evaluated += 1
        if result.p50_periods >= horizon_periods:
            within_p50 += 1
        if result.p85_periods >= horizon_periods:
            within_p85 += 1

    if evaluated == 0:
        return Backtest(
            cutoffs=0,
            evaluated=0,
            p50_coverage=None,
            p85_coverage=None,
            seed=seed,
            reasons=("nenhum corte utilizável: sem entregas observadas no horizonte",),
        )
    return Backtest(
        cutoffs=evaluated,
        evaluated=evaluated,
        p50_coverage=Decimal(within_p50) / Decimal(evaluated),
        p85_coverage=Decimal(within_p85) / Decimal(evaluated),
        seed=seed,
        reasons=(
            "cobertura empírica medida em cortes sem vazamento de futuro; status experimental",
        ),
    )
