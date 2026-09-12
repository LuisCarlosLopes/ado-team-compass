"""Disponibilidade por métrica: requisitos, status, cobertura e motivo (plano 4.1.2 a 4.1.4).

Este módulo decide se um resultado é utilizável para o perfil da equipe. Ele não produz
nenhum score agregado e não existe "percentual de confiança": cada métrica carrega seu
próprio status, sua cobertura de itens e o motivo da indisponibilidade.

Cobertura é cobertura de itens elegíveis, nunca cobertura do esforço desconhecido.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ado_team_compass.contracts.common import (
    Capability,
    Coverage,
    MetricStatus,
    QualityCounters,
    Quantity,
)
from ado_team_compass.contracts.config import TeamConfig
from ado_team_compass.contracts.metrics import Metric

__all__ = ["METRIC_REQUIREMENTS", "MetricRequirement", "assess_metric", "requirement"]


@dataclass(frozen=True)
class MetricRequirement:
    """Requisitos declarados de uma métrica e o motivo de não ser aplicável."""

    metric_id: str
    definition_version: str
    capability: Capability
    required_process_fields: tuple[str, ...] = ()
    requires_reservations: bool = False
    zero_is_meaningful: bool = False
    not_applicable_reason: str = "métrica não aplicável ao perfil desta equipe"
    notes: tuple[str, ...] = field(default_factory=tuple)

    def missing_process_fields(self, team: TeamConfig) -> tuple[str, ...]:
        return tuple(
            name for name in self.required_process_fields if getattr(team.process, name) is None
        )


METRIC_REQUIREMENTS: dict[str, MetricRequirement] = {
    "open_items_count": MetricRequirement(
        metric_id="open_items_count",
        definition_version="1.0",
        capability=Capability.CURRENT_STATUS,
        zero_is_meaningful=True,
    ),
    "blocked_items_count": MetricRequirement(
        metric_id="blocked_items_count",
        definition_version="1.0",
        capability=Capability.CURRENT_STATUS,
        zero_is_meaningful=True,
        not_applicable_reason="origem de impedimento não configurada para esta equipe",
    ),
    "known_remaining_work": MetricRequirement(
        metric_id="known_remaining_work",
        definition_version="1.0",
        capability=Capability.ALLOCATION,
        required_process_fields=("remaining_work_field",),
        not_applicable_reason="a equipe não registra trabalho restante",
    ),
    "reserved_remaining_capacity": MetricRequirement(
        metric_id="reserved_remaining_capacity",
        definition_version="1.0",
        capability=Capability.ALLOCATION,
        requires_reservations=True,
        not_applicable_reason="a equipe não mantém capacidade reservada",
    ),
    "observed_utilization": MetricRequirement(
        metric_id="observed_utilization",
        definition_version="1.0",
        capability=Capability.ALLOCATION,
        required_process_fields=("remaining_work_field",),
        requires_reservations=True,
        not_applicable_reason="utilização exige carga e capacidade na mesma unidade e janela",
    ),
}


def requirement(metric_id: str) -> MetricRequirement:
    return METRIC_REQUIREMENTS[metric_id]


def assess_metric(
    metric_id: str,
    team: TeamConfig,
    *,
    counters: QualityCounters,
    quantity: Quantity | None = None,
    has_reservations: bool = False,
    extra_reasons: tuple[str, ...] = (),
) -> Metric:
    """Classifica a métrica como `available`, `partial`, `unavailable` ou `not_applicable`.

    Ausência de campo aplicável ao perfil resulta em `not_applicable` com motivo, nunca em
    zero e nunca em achado de higiene. Denominador desconhecido nunca produz cobertura total.
    """
    spec = requirement(metric_id)
    reasons = tuple(dict.fromkeys((*counters.reasons, *extra_reasons)))
    coverage = Coverage(eligible=counters.eligible, valid=counters.known)

    not_applicable = _not_applicable_reason(spec, team, has_reservations=has_reservations)
    if not_applicable is not None:
        return Metric(
            id=spec.metric_id,
            definition_version=spec.definition_version,
            status=MetricStatus.NOT_APPLICABLE,
            coverage=Coverage(),
            quality=counters.model_copy(update={"reasons": reasons}),
            unavailable_reason=not_applicable,
        )

    status, unavailable_reason = _status(spec, counters, coverage)
    return Metric(
        id=spec.metric_id,
        definition_version=spec.definition_version,
        status=status,
        quantity=quantity if status is not MetricStatus.UNAVAILABLE else None,
        coverage=coverage,
        quality=counters.model_copy(update={"reasons": reasons}),
        unavailable_reason=unavailable_reason,
    )


def _not_applicable_reason(
    spec: MetricRequirement, team: TeamConfig, *, has_reservations: bool
) -> str | None:
    if spec.capability not in team.capabilities:
        return (
            f"capacidade {spec.capability.value} não habilitada para a equipe "
            f"{team.alias!r}: {spec.not_applicable_reason}"
        )
    missing = spec.missing_process_fields(team)
    if missing:
        return (
            f"{spec.not_applicable_reason}; campos de processo não configurados: "
            f"{', '.join(missing)}"
        )
    if spec.requires_reservations and not has_reservations:
        return spec.not_applicable_reason
    return None


def _status(
    spec: MetricRequirement, counters: QualityCounters, coverage: Coverage
) -> tuple[MetricStatus, str | None]:
    if counters.eligible is None:
        return MetricStatus.PARTIAL, None
    if counters.eligible == 0:
        if spec.zero_is_meaningful:
            return MetricStatus.AVAILABLE, None
        return (
            MetricStatus.UNAVAILABLE,
            "amostra elegível vazia: nenhum item sustenta esta métrica",
        )
    if counters.known == 0:
        return (
            MetricStatus.UNAVAILABLE,
            "nenhum item elegível possui valor válido para esta métrica",
        )
    if coverage.valid < counters.eligible:
        return MetricStatus.PARTIAL, None
    return MetricStatus.AVAILABLE, None
