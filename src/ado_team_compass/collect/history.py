"""Coleta de histórico pelas revisões expostas pelo MCP oficial (T17).

Sem ferramenta de revisões no catálogo conectado, o histórico fica indisponível: nenhuma
consulta REST, OData ou WIQL direta é usada como alternativa, e nenhuma série é reconstruída
a partir da última alteração genérica.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from ado_team_compass.adapters.ado_mcp import AdoMcpClient, Operation
from ado_team_compass.collect.normalization import entries
from ado_team_compass.contracts.common import Provenance
from ado_team_compass.contracts.config import TeamConfig
from ado_team_compass.contracts.history import HistoryCoverage, HistorySet, ItemRevision
from ado_team_compass.errors import CapabilityUnavailable, CollectError

__all__ = ["collect_history", "normalize_revision"]


def normalize_revision(
    entry: Mapping[str, Any],
    *,
    team: TeamConfig,
    item_id: int,
    provenance: Provenance | None = None,
) -> ItemRevision | None:
    """Converte uma revisão do MCP; revisão sem data utilizável é descartada."""
    nested = entry.get("fields")
    fields: Mapping[str, Any] = nested if isinstance(nested, Mapping) else entry
    changed_at = _moment(fields.get("System.ChangedDate") or entry.get("changedDate"))
    if changed_at is None:
        return None
    revision = entry.get("rev") or entry.get("revision") or 0
    state = _text(fields.get("System.State"))
    return ItemRevision(
        item_id=item_id,
        revision=int(revision) if isinstance(revision, int) else 0,
        changed_at=changed_at,
        state=state,
        state_category=team.process.state_categories.get(state) if state else None,
        iteration_path=_text(fields.get("System.IterationPath")),
        area_path=_text(fields.get("System.AreaPath")),
        assigned_to=_person(fields.get("System.AssignedTo")),
        story_points=_decimal(fields.get(team.process.story_points_field or "")),
        remaining_work=_decimal(fields.get(team.process.remaining_work_field or "")),
        provenance=provenance,
    )


def collect_history(
    client: AdoMcpClient,
    team: TeamConfig,
    item_ids: Sequence[int],
    *,
    collected_at: datetime,
) -> HistorySet:
    """Coleta revisões dos itens informados e declara a cobertura alcançada."""
    reasons: list[str] = []
    revisions: list[ItemRevision] = []
    with_revisions = 0

    if not item_ids:
        return HistorySet(
            collected_at=collected_at,
            coverage=HistoryCoverage(reasons=("nenhum item no escopo para coletar histórico",)),
        )

    for item_id in item_ids:
        provenance = Provenance(
            source="mcp",
            tool="list_work_item_revisions",
            action="read",
            collected_at=collected_at,
            references=(f"evidence/items/{item_id}.json",),
        )
        try:
            payload = client.call(
                Operation.LIST_WORK_ITEM_REVISIONS,
                {"project": team.project_id, "id": item_id},
            )
        except CapabilityUnavailable as error:
            return HistorySet(
                collected_at=collected_at,
                coverage=HistoryCoverage(
                    requested_items=len(item_ids),
                    reasons=(f"histórico indisponível no catálogo conectado: {error.message}",),
                ),
            )
        except CollectError as error:
            reasons.append(f"item {item_id}: revisões não coletadas ({error.code})")
            continue

        normalized = [
            revision
            for entry in entries(payload, "revisions", "value")
            if (
                revision := normalize_revision(
                    entry, team=team, item_id=item_id, provenance=provenance
                )
            )
            is not None
        ]
        if normalized:
            with_revisions += 1
            revisions.extend(normalized)
        else:
            reasons.append(f"item {item_id}: nenhuma revisão utilizável na resposta")

    coverage = HistoryCoverage(
        requested_items=len(item_ids),
        items_with_revisions=with_revisions,
        intraday_events=_has_intraday(revisions),
        includes_removed_items=False,
        includes_items_moved_out=False,
        reasons=tuple(
            dict.fromkeys(
                (
                    *reasons,
                    "itens excluídos e itens movidos para fora do escopo não são descobertos "
                    "por revisões dos itens conhecidos",
                )
            )
        ),
    )
    return HistorySet(collected_at=collected_at, revisions=tuple(revisions), coverage=coverage)


def _has_intraday(revisions: Sequence[ItemRevision]) -> bool:
    """Indica se há mais de uma revisão do mesmo item no mesmo dia."""
    seen: set[tuple[int, str]] = set()
    for revision in revisions:
        key = (revision.item_id, revision.changed_at.date().isoformat())
        if key in seen:
            return True
        seen.add(key)
    return False


def _moment(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def _text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _person(value: Any) -> str | None:
    if isinstance(value, Mapping):
        for key in ("id", "uniqueName", "descriptor"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return None
    return _text(value)


def _decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return Decimal(str(value))
    if isinstance(value, str) and value.strip():
        try:
            return Decimal(value.strip())
        except ArithmeticError:
            return None
    return None
