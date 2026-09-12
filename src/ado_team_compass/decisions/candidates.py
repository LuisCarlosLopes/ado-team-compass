"""Candidatos de ação derivados dos números da execução (docs/sprint-report.md §3).

Um candidato é uma sugestão com evidência e condição a confirmar. Ele nunca é executado,
nunca estima benefício e nunca conclui ociosidade: "sem carga registrada" pede verificação,
não reatribuição. A ordenação é explícita e determinística; empate usa o ID estável.
"""

from __future__ import annotations

from decimal import Decimal

from ado_team_compass.contracts.decisions import ActionCandidate
from ado_team_compass.contracts.report import TeamReport

__all__ = ["MAX_PRIORITY_DECISIONS", "build_candidates"]

#: O relatório destaca no máximo três decisões prioritárias.
MAX_PRIORITY_DECISIONS = 3

_PRIORITY_IMPEDIMENT = 1
_PRIORITY_CAPACITY = 2
_PRIORITY_WIP = 3
_PRIORITY_MISSING_DATA = 4


def build_candidates(
    report: TeamReport, *, blocked_item_ids: tuple[int, ...] = ()
) -> tuple[ActionCandidate, ...]:
    """Gera os candidatos na ordem de prioridade do contrato do relatório."""
    candidates: list[ActionCandidate] = []
    candidates.extend(_impediments(report, blocked_item_ids))
    candidates.extend(_capacity_deficit(report))
    candidates.extend(_missing_estimates(report))
    candidates.extend(_no_recorded_load(report))
    return tuple(sorted(candidates, key=lambda item: (item.priority, item.id)))


def _impediments(report: TeamReport, blocked_item_ids: tuple[int, ...]) -> list[ActionCandidate]:
    if not blocked_item_ids:
        return []
    return [
        ActionCandidate(
            id=f"impediment:{report.team_id}",
            rule_id="active_impediment",
            priority=_PRIORITY_IMPEDIMENT,
            problem=(
                f"{len(blocked_item_ids)} itens estão marcados como impedidos pela origem "
                "configurada."
            ),
            observed_impact="Entregas com impedimento registrado não avançam sem desbloqueio.",
            action="Acionar quem está registrado como responsável pela resolução.",
            decision_role="responsável pela entrega",
            to_confirm=(
                "confirmar o vínculo com o objetivo e a causa do bloqueio; ausência de "
                "registro não prova ausência de impedimento, e o responsável pela resolução "
                "não é inferido do responsável pelo item"
            ),
            verification="o item sai do estado impedido e volta a avançar",
            item_ids=blocked_item_ids,
            evidence=tuple(f"evidence/items/{item_id}.json" for item_id in blocked_item_ids),
        )
    ]


def _capacity_deficit(report: TeamReport) -> list[ActionCandidate]:
    load = report.metric("known_remaining_work")
    capacity = report.metric("reserved_remaining_capacity")
    if load is None or capacity is None:
        return []
    if load.quantity is None or load.quantity.value is None:
        return []
    if capacity.quantity is None or capacity.quantity.value is None:
        return []
    if load.quantity.unit != capacity.quantity.unit:
        return []
    gap = load.quantity.value - capacity.quantity.value
    if gap <= 0:
        return []
    partial = load.coverage.eligible is not None and load.coverage.valid < load.coverage.eligible
    unit = load.quantity.unit
    return [
        ActionCandidate(
            id=f"capacity_gap:{report.team_id}",
            rule_id="known_load_above_capacity",
            priority=_PRIORITY_CAPACITY,
            problem=(f"O gap conhecido de capacidade é +{_fmt(gap)} {unit} na janela analisada."),
            observed_impact=(
                f"Carga conhecida {_fmt(load.quantity.value)} {unit} contra capacidade restante "
                f"reservada {_fmt(capacity.quantity.value)} {unit}"
                + (
                    "; o valor é um limite inferior porque há itens abertos sem estimativa."
                    if partial
                    else "."
                )
            ),
            action="Negociar escopo, fatiar a entrega ou redistribuir o trabalho conhecido.",
            decision_role="pessoa responsável pelo produto e equipe",
            to_confirm=(
                "validar dependências, habilidades e prioridade antes de transferir trabalho; "
                "o gap não prevê data de atraso"
            ),
            verification="o gap conhecido cai na próxima coleta com a mesma janela e unidade",
            evidence=("known_remaining_work", "reserved_remaining_capacity"),
        )
    ]


def _missing_estimates(report: TeamReport) -> list[ActionCandidate]:
    load = report.metric("known_remaining_work")
    if load is None or not load.quality.missing:
        return []
    return [
        ActionCandidate(
            id=f"missing_remaining_work:{report.team_id}",
            rule_id="missing_remaining_work",
            priority=_PRIORITY_MISSING_DATA,
            problem=(f"{load.quality.missing} itens abertos não têm trabalho restante registrado."),
            observed_impact=(
                "Sem esses valores, a carga conhecida é um limite inferior e a utilização "
                "observada permanece parcial."
            ),
            action="Atualizar a estimativa de trabalho restante dos itens listados.",
            decision_role="pessoas responsáveis pelos itens",
            to_confirm=(
                "confirmar se os itens seguem no escopo; não imputar OriginalEstimate como "
                "trabalho restante"
            ),
            verification="a cobertura da métrica de carga chega a 100% dos itens elegíveis",
            evidence=("known_remaining_work",),
        )
    ]


def _no_recorded_load(report: TeamReport) -> list[ActionCandidate]:
    people = [
        row
        for row in report.people
        if row.load_class == "SEM_CARGA_REGISTRADA" and row.person_id != "(sem responsável)"
    ]
    if not people:
        return []
    return [
        ActionCandidate(
            id=f"no_recorded_load:{report.team_id}",
            rule_id="no_recorded_load",
            priority=_PRIORITY_WIP,
            problem=f"{len(people)} pessoas não têm carga registrada na janela observada.",
            observed_impact=(
                "O board observado não registra trabalho aberto para essas pessoas nesta janela."
            ),
            action="Verificar com a pessoa o trabalho fora do board e a disponibilidade real.",
            decision_role="liderança da equipe",
            to_confirm=(
                "ausência de registro não é ociosidade; não reatribuir trabalho automaticamente"
            ),
            verification="o trabalho em andamento passa a estar visível ou a ausência é explicada",
            evidence=("known_remaining_work",),
        )
    ]


def _fmt(value: Decimal) -> str:
    quantized = value.quantize(Decimal("0.01"))
    text = f"{quantized}"
    return text.rstrip("0").rstrip(".") if "." in text else text
