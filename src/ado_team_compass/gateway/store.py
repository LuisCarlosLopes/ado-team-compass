"""Leitura dos relatórios já produzidos, para o gateway (T28).

O repositório só lê o volume de execuções gravado pelo coletor. Ele nunca fabrica dados: se
não existe relatório, a resposta é 404; se o relatório é antigo, ele mantém o instante de
referência e acrescenta um aviso de atualidade.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from ado_team_compass.contracts.report import TeamReport
from ado_team_compass.errors import CompassError
from ado_team_compass.runs import RunStore
from ado_team_compass.runs.store import StoredRun

__all__ = ["DEFAULT_STALE_AFTER", "ReportEnvelope", "ReportRepository"]

#: Acima disso, o relatório é servido com aviso de atualidade, nunca fabricado de novo.
DEFAULT_STALE_AFTER = timedelta(hours=26)


@dataclass(frozen=True)
class ReportEnvelope:
    """Relatório com metadados de atualidade e limitações."""

    report: TeamReport
    run_id: str
    state: str
    as_of: datetime
    collected_at: datetime | None
    is_stale: bool
    staleness_note: str | None
    partial_reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "state": self.state,
            "as_of": self.as_of.isoformat(),
            "collected_at": self.collected_at.isoformat() if self.collected_at else None,
            "is_stale": self.is_stale,
            "staleness_note": self.staleness_note,
            "partial_reasons": list(self.partial_reasons),
            "report": self.report.model_dump(mode="json"),
        }


@dataclass
class ReportRepository:
    """Acesso somente leitura ao volume de execuções."""

    store: RunStore
    stale_after: timedelta = DEFAULT_STALE_AFTER

    def teams(self) -> tuple[str, ...]:
        """Equipes com pelo menos uma execução persistida."""
        aliases: list[str] = []
        for run_id in self.store.list_runs():
            alias = run_id.split("-", 1)[1] if "-" in run_id else run_id
            if alias not in aliases:
                aliases.append(alias)
        return tuple(sorted(aliases))

    def latest(self, team_alias: str, *, now: datetime) -> ReportEnvelope | None:
        run = self.store.latest(team_alias)
        if run is None:
            return None
        return self._envelope(run, now=now)

    def by_run_id(self, run_id: str, *, now: datetime) -> ReportEnvelope | None:
        try:
            run = self.store.load(run_id)
        except CompassError:
            return None
        return self._envelope(run, now=now)

    def team_of(self, run_id: str) -> str | None:
        """Equipe dona da execução; um run ID sozinho nunca autoriza acesso."""
        envelope = self.by_run_id(run_id, now=datetime.now(tz=None))
        return envelope.report.team_alias if envelope else None

    def evidence(self, run_id: str, reference: str) -> dict[str, Any] | None:
        try:
            run = self.store.load(run_id)
        except CompassError:
            return None
        if not reference.isdigit():
            return None
        path = run.directory / "evidence" / "items" / f"{reference}.json"
        if not path.is_file():
            return None
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None

    def _envelope(self, run: StoredRun, *, now: datetime) -> ReportEnvelope:
        report = TeamReport.model_validate(run.artifact("report.json"))
        as_of = run.manifest.as_of
        age = now - as_of if now.tzinfo == as_of.tzinfo else None
        is_stale = bool(age and age > self.stale_after)
        note = None
        if is_stale and age is not None:
            hours = int(age.total_seconds() // 3600)
            note = (
                f"relatório com {hours} horas: os números são do instante de referência "
                "informado e não foram atualizados"
            )
        return ReportEnvelope(
            report=report,
            run_id=run.manifest.run_id,
            state=run.manifest.state.value,
            as_of=as_of,
            collected_at=run.manifest.collection_finished_at,
            is_stale=is_stale,
            staleness_note=note,
            partial_reasons=run.manifest.partial_reasons,
        )
