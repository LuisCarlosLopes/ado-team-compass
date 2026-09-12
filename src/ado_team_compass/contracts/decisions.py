"""Contrato de `decisions.json`: registro humano exportável, sem escrita no ADO."""

from __future__ import annotations

from datetime import date, datetime

from ado_team_compass.contracts.common import StrictModel

__all__ = ["Decision", "DecisionLog"]


class Decision(StrictModel):
    """Ação humana registrada; não altera snapshots nem work items."""

    id: str
    origin_run_id: str
    finding_id: str | None = None
    statement: str
    owner: str | None = None
    due_date: date | None = None
    status: str = "open"
    evidence: tuple[str, ...] = ()
    recorded_at: datetime
    recorded_by: str


class DecisionLog(StrictModel):
    decisions: tuple[Decision, ...] = ()

    def deduplicated(self) -> tuple[Decision, ...]:
        """Mantém a primeira ocorrência de cada ID estável, preservando a ordem."""
        seen: set[str] = set()
        kept: list[Decision] = []
        for decision in self.decisions:
            if decision.id in seen:
                continue
            seen.add(decision.id)
            kept.append(decision)
        return tuple(kept)
