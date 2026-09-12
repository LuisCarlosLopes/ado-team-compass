"""Validação da interpretação produzida por um modelo de linguagem (plano 4.1.3 e 5).

A narrativa é opcional e nunca cria números. Cada trecho passa por três verificações:

1. referências existem na execução (métrica conhecida, item com evidência);
2. todo número citado aparece entre os valores calculados da execução;
3. nenhuma afirmação de ociosidade real, culpa, causalidade demonstrada ou ranking
   individual é aceita.

Trecho reprovado é descartado com motivo; o relatório determinístico permanece utilizável.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from ado_team_compass.contracts.narrative import Narrative, NarrativeAction, NarrativeHypothesis
from ado_team_compass.contracts.report import TeamReport

__all__ = ["BANNED_CLAIMS", "MAX_ACTIONS", "validate_narrative"]

#: Ações sugeridas são candidatas e limitadas (plano 4.1.4).
MAX_ACTIONS = 3

BANNED_CLAIMS = (
    r"ocios[oa]s?\b",
    r"ociosidade",
    r"sem fazer nada",
    r"mais produtiv[oa]",
    r"menos produtiv[oa]",
    r"\branking\b",
    r"pior desempenho",
    r"melhor desempenho",
    r"culpa\b",
    r"culpad[oa]",
    r"prova que",
    r"comprova que",
    r"é causad[oa] por",
    r"foi causad[oa] por",
)
_BANNED = re.compile("|".join(BANNED_CLAIMS), re.IGNORECASE)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def validate_narrative(
    candidate: Mapping[str, Any],
    report: TeamReport,
) -> Narrative:
    """Aceita apenas o que é rastreável; devolve os trechos reprovados com o motivo."""
    rejected: list[str] = []
    allowed_numbers = _allowed_numbers(report)
    known_metrics = {metric.id for metric in report.metrics}
    known_items = {int(item_id) for item_id in report.evidence_references}

    hypotheses: list[NarrativeHypothesis] = []
    for raw in _sequence(candidate.get("hypotheses")):
        statement = str(raw.get("statement", "")).strip()
        references = tuple(str(item) for item in _sequence(raw.get("references")))
        problem = _problem(statement, references, allowed_numbers, known_metrics, known_items)
        if problem:
            rejected.append(f"hipótese rejeitada ({problem}): {statement}")
            continue
        hypotheses.append(
            NarrativeHypothesis(
                statement=statement,
                references=references,
                confidence_note=_optional(raw.get("confidence_note")),
            )
        )

    actions: list[NarrativeAction] = []
    for raw in _sequence(candidate.get("actions")):
        statement = str(raw.get("statement", "")).strip()
        references = tuple(str(item) for item in _sequence(raw.get("references")))
        condition = _optional(raw.get("condition_to_confirm"))
        problem = _problem(statement, references, allowed_numbers, known_metrics, known_items)
        if problem is None and not condition:
            problem = "ação sem condição a confirmar"
        if problem:
            rejected.append(f"ação rejeitada ({problem}): {statement}")
            continue
        if len(actions) >= MAX_ACTIONS:
            rejected.append(f"ação rejeitada (limite de {MAX_ACTIONS} ações): {statement}")
            continue
        actions.append(
            NarrativeAction(
                statement=statement, references=references, condition_to_confirm=str(condition)
            )
        )

    accepted_references: list[str] = []
    for hypothesis in hypotheses:
        accepted_references.extend(hypothesis.references)
    for action in actions:
        accepted_references.extend(action.references)
    referenced_metrics = tuple(
        sorted({reference for reference in accepted_references if reference in known_metrics})
    )
    referenced_items = tuple(
        sorted(
            {
                int(match)
                for reference in accepted_references
                for match in re.findall(r"evidence/items/(\d+)\.json", reference)
            }
        )
    )
    return Narrative(
        run_id=report.run_id,
        referenced_metric_ids=referenced_metrics,
        referenced_item_ids=referenced_items,
        hypotheses=tuple(hypotheses),
        actions=tuple(actions),
        rejected_fragments=tuple(rejected),
    )


def _problem(
    statement: str,
    references: Sequence[str],
    allowed_numbers: set[Decimal],
    known_metrics: set[str],
    known_items: set[int],
) -> str | None:
    if not statement:
        return "trecho vazio"
    if _BANNED.search(statement):
        return "afirmação de ociosidade, culpa, causalidade ou comparação individual"
    if not references:
        return "trecho sem referência"
    for reference in references:
        if reference in known_metrics:
            continue
        match = re.fullmatch(r"evidence/items/(\d+)\.json", reference)
        if match and int(match.group(1)) in known_items:
            continue
        return f"referência inexistente na execução: {reference}"
    for token in _NUMBER.findall(statement):
        value = _decimal(token)
        if value is None or value not in allowed_numbers:
            return f"número sem correspondência na execução: {token}"
    return None


def _allowed_numbers(report: TeamReport) -> set[Decimal]:
    """Números que a execução realmente produziu, incluindo percentuais arredondados."""
    allowed: set[Decimal] = set()
    for metric in report.metrics:
        if metric.quantity is not None and metric.quantity.value is not None:
            allowed.add(metric.quantity.value)
        if metric.ratio is not None:
            allowed.update(_ratio_forms(metric.ratio))
        if metric.coverage.eligible is not None:
            allowed.add(Decimal(metric.coverage.eligible))
        allowed.add(Decimal(metric.coverage.valid))
        allowed.add(Decimal(metric.quality.missing))
        allowed.add(Decimal(metric.quality.invalid))
        allowed.add(Decimal(metric.quality.excluded))
    for row in report.people:
        if row.known_load.value is not None:
            allowed.add(row.known_load.value)
        if row.reserved_capacity is not None and row.reserved_capacity.value is not None:
            allowed.add(row.reserved_capacity.value)
        if row.utilization is not None:
            allowed.update(_ratio_forms(row.utilization))
        allowed.update(
            {
                Decimal(row.items_eligible),
                Decimal(row.items_known),
                Decimal(row.items_missing),
            }
        )
    allowed.update(Decimal(item_id) for item_id in report.evidence_references)
    for finding in report.findings:
        allowed.update(Decimal(item_id) for item_id in finding.item_ids)
    return {value.normalize() for value in allowed}


def _ratio_forms(ratio: Decimal) -> set[Decimal]:
    percent = ratio * 100
    return {
        ratio.normalize(),
        percent.normalize(),
        percent.quantize(Decimal("1")).normalize(),
        percent.quantize(Decimal("0.1")).normalize(),
    }


def _decimal(token: str) -> Decimal | None:
    try:
        return Decimal(token.replace(",", ".")).normalize()
    except InvalidOperation:
        return None


def _sequence(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, list):
        return [entry for entry in value if isinstance(entry, Mapping | str)]  # type: ignore[misc]
    return []


def _optional(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
