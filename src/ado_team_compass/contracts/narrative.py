"""Contrato de `narrative.json`: interpretação validada contra fatos referenciados."""

from __future__ import annotations

from ado_team_compass.contracts.common import StrictModel

__all__ = ["Narrative", "NarrativeAction", "NarrativeHypothesis"]


class NarrativeHypothesis(StrictModel):
    """Hipótese: exige referências e nunca afirma causalidade demonstrada."""

    statement: str
    references: tuple[str, ...]
    confidence_note: str | None = None


class NarrativeAction(StrictModel):
    """Ação candidata, nunca automática, com evidência e condição a confirmar."""

    statement: str
    references: tuple[str, ...]
    condition_to_confirm: str


class Narrative(StrictModel):
    run_id: str
    referenced_metric_ids: tuple[str, ...] = ()
    referenced_item_ids: tuple[int, ...] = ()
    hypotheses: tuple[NarrativeHypothesis, ...] = ()
    actions: tuple[NarrativeAction, ...] = ()
    rejected_fragments: tuple[str, ...] = ()
