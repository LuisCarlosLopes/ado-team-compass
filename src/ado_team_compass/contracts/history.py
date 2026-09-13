"""Contratos de histórico: revisões de item e cobertura da série (plano 4.1.5).

Revisões conhecidas não provam descoberta completa: itens excluídos ou movidos para fora do
escopo podem não aparecer. Por isso toda série carrega sua cobertura e o motivo do que falta.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from ado_team_compass.contracts.common import Provenance, StrictModel
from ado_team_compass.contracts.config import StateCategory

__all__ = ["HistoryCoverage", "HistorySet", "ItemRevision"]


class ItemRevision(StrictModel):
    """Uma revisão observada de um item, já normalizada."""

    item_id: int
    revision: int
    changed_at: datetime
    state: str | None = None
    state_category: StateCategory | None = None
    iteration_path: str | None = None
    area_path: str | None = None
    assigned_to: str | None = None
    story_points: Decimal | None = None
    remaining_work: Decimal | None = None
    provenance: Provenance | None = None


class HistoryCoverage(StrictModel):
    """O que a coleta histórica alcançou e o que permanece desconhecido."""

    requested_items: int = 0
    items_with_revisions: int = 0
    intraday_events: bool = False
    includes_removed_items: bool = False
    includes_items_moved_out: bool = False
    reasons: tuple[str, ...] = ()

    @property
    def is_usable(self) -> bool:
        """Série utilizável exige revisões de todos os itens pedidos."""
        return self.requested_items > 0 and self.items_with_revisions == self.requested_items


class HistorySet(StrictModel):
    """Revisões coletadas de uma janela, com cobertura declarada."""

    collected_at: datetime
    revisions: tuple[ItemRevision, ...] = ()
    coverage: HistoryCoverage = Field(default_factory=HistoryCoverage)

    def for_item(self, item_id: int) -> tuple[ItemRevision, ...]:
        """Revisões de um item em ordem cronológica estável."""
        return tuple(
            sorted(
                (revision for revision in self.revisions if revision.item_id == item_id),
                key=lambda revision: (revision.changed_at, revision.revision),
            )
        )

    def item_ids(self) -> tuple[int, ...]:
        return tuple(sorted({revision.item_id for revision in self.revisions}))
