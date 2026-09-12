"""Resumo para interpretação, com redução determinística de tamanho.

Totais e limitações nunca são cortados: quando o resumo excede o limite, os achados são
selecionados por severidade e ID, e o restante fica referenciado pela execução.
"""

from __future__ import annotations

import json

from ado_team_compass.contracts.metrics import Finding, Summary
from ado_team_compass.contracts.report import TeamReport

__all__ = ["SEVERITY_ORDER", "build_summary"]

SEVERITY_ORDER = {"critico": 0, "alto": 1, "atencao": 2, "info": 3}


def _rank(finding: Finding) -> tuple[int, str, str]:
    return (SEVERITY_ORDER.get(finding.severity, 99), finding.rule_id, finding.id)


def build_summary(report: TeamReport, *, limit_bytes: int = 24576) -> Summary:
    """Monta o resumo e reduz os achados até caber, preservando métricas e limitações."""
    ordered = sorted(report.findings, key=_rank)
    summary = Summary(
        run_id=report.run_id,
        team_id=report.team_id,
        metrics=report.metrics,
        findings=tuple(ordered),
        limitations=report.limitations,
        truncated=False,
        size_limit_bytes=limit_bytes,
    )
    if _size(summary) <= limit_bytes:
        return summary

    kept = list(ordered)
    while kept:
        kept.pop()
        candidate = summary.model_copy(
            update={
                "findings": tuple(kept),
                "truncated": True,
                "truncation_reference": (
                    f"achados completos em {report.run_id}/metrics.json ({len(ordered)} achados)"
                ),
            }
        )
        if _size(candidate) <= limit_bytes:
            return candidate
    return summary.model_copy(
        update={
            "findings": (),
            "truncated": True,
            "truncation_reference": f"achados completos em {report.run_id}/metrics.json",
        }
    )


def _size(summary: Summary) -> int:
    payload = json.dumps(summary.model_dump(mode="json"), ensure_ascii=False)
    return len(payload.encode("utf-8"))
