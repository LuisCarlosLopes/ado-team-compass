"""Evidência minimizada: o suficiente para explicar um total, nada além disso.

Nenhuma credencial e nenhuma descrição integral entram na evidência. O título aparece como
excerto curto, com caracteres de controle removidos, porque é texto vindo da fonte.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ado_team_compass.contracts.facts import WorkItemFact

__all__ = ["TITLE_EXCERPT_LIMIT", "minimize_item", "write_evidence"]

TITLE_EXCERPT_LIMIT = 80
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _excerpt(value: str | None) -> str | None:
    if value is None:
        return None
    clean = _CONTROL.sub(" ", value).strip()
    if len(clean) <= TITLE_EXCERPT_LIMIT:
        return clean
    return clean[: TITLE_EXCERPT_LIMIT - 1] + "…"


def minimize_item(item: WorkItemFact) -> dict[str, Any]:
    """Registro mínimo que permite reconciliar um total até o item de origem."""
    return {
        "id": item.id,
        "organization": item.organization,
        "project_id": item.project_id,
        "item_type": item.item_type,
        "state": item.state,
        "state_category": item.state_category.value if item.state_category else None,
        "title_excerpt": _excerpt(item.title),
        "assigned_to": item.assigned_to,
        "area_path": item.area_path,
        "iteration_path": item.iteration_path,
        "activity": item.activity,
        "blocked": item.blocked,
        "remaining_work": _quantity(item.remaining_work),
        "original_estimate": _quantity(item.original_estimate),
        "completed_work": _quantity(item.completed_work),
        "story_points": str(item.story_points) if item.story_points is not None else None,
        "changed_at": item.changed_at.isoformat() if item.changed_at else None,
        "team_memberships": list(item.team_memberships),
        "provenance": {
            "source": item.provenance.source,
            "tool": item.provenance.tool,
            "action": item.provenance.action,
            "collected_at": item.provenance.collected_at.isoformat(),
        },
    }


def _quantity(quantity: Any) -> dict[str, Any] | None:
    if quantity is None:
        return None
    return {
        "value": str(quantity.value) if quantity.value is not None else None,
        "unit": quantity.unit,
    }


def write_evidence(directory: Path, items: Sequence[WorkItemFact]) -> dict[str, str]:
    """Grava um arquivo por item e devolve a referência usada nas métricas."""
    target = directory / "evidence" / "items"
    target.mkdir(parents=True, exist_ok=True)
    references: dict[str, str] = {}
    for item in items:
        payload = minimize_item(item)
        path = target / f"{item.id}.json"
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
        references[str(item.id)] = f"evidence/items/{item.id}.json"
    return references
