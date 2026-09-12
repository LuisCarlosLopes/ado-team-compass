"""Orquestração da execução: coletar, calcular, persistir e renderizar.

Sequência (plano 4.2): validar entrada → resolver configuração → verificar capacidades →
coletar escopo autorizado → normalizar com cobertura → calcular com relógio fixado →
persistir por escrita atômica → gerar relatório determinístico → devolver artefatos e status.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ado_team_compass.adapters.ado_mcp import AdoMcpClient
from ado_team_compass.collect import collect_current_status
from ado_team_compass.config.loader import ResolvedConfig
from ado_team_compass.contracts.common import Window
from ado_team_compass.contracts.config import TeamConfig
from ado_team_compass.contracts.facts import FactSet
from ado_team_compass.contracts.metrics import MetricSet
from ado_team_compass.contracts.report import TeamReport
from ado_team_compass.contracts.run import RunState
from ado_team_compass.errors import CompassError, ConfigError, ExitCode
from ado_team_compass.metrics.engine import build_team_report
from ado_team_compass.reporting import build_summary, render_markdown
from ado_team_compass.runs import RunStore, write_evidence
from ado_team_compass.runs.store import StoredRun, run_id_for

__all__ = ["RunOutcome", "execute_status", "replay_run", "source_identity"]


@dataclass(frozen=True)
class RunOutcome:
    """Execução persistida, relatório calculado e código de saída correspondente."""

    run: StoredRun
    report: TeamReport
    exit_code: ExitCode
    markdown: str


def source_identity(*parts: str) -> str:
    """Identidade opaca da fonte: nunca guarda nome de pessoa nem credencial."""
    canonical = "|".join(parts)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def execute_status(
    client: AdoMcpClient,
    team: TeamConfig,
    *,
    organization: str,
    as_of: datetime,
    store: RunStore,
    resolved: ResolvedConfig,
    iteration_path: str | None = None,
) -> RunOutcome:
    """Coleta, calcula e persiste uma execução completa da situação atual."""
    run_id = run_id_for(as_of, team.alias)
    directory = store.begin(run_id)
    started_at = as_of
    catalog = client.catalog
    try:
        collection = collect_current_status(
            client,
            team,
            organization=organization,
            as_of=as_of,
            iteration_path=iteration_path,
        )
    except CompassError as error:
        store.abandon(directory, f"{error.code}: {error.message}")
        raise

    try:
        outcome = _persist(
            store,
            directory,
            run_id=run_id,
            team=team,
            resolved=resolved,
            facts=collection.facts,
            window=collection.window,
            iteration_path=collection.iteration_path,
            as_of=as_of,
            started_at=started_at,
            organization=organization,
            catalog_hash=catalog.catalog_hash if catalog else None,
            server_version=catalog.server_version if catalog else None,
            extra_limitations=collection.reasons,
        )
    except CompassError as error:
        store.abandon(directory, f"{error.code}: {error.message}")
        raise
    return outcome


def _persist(
    store: RunStore,
    directory: Path,
    *,
    run_id: str,
    team: TeamConfig,
    resolved: ResolvedConfig,
    facts: FactSet,
    window: Window | None,
    iteration_path: str | None,
    as_of: datetime,
    started_at: datetime,
    organization: str,
    catalog_hash: str | None,
    server_version: str | None,
    extra_limitations: tuple[str, ...] = (),
) -> RunOutcome:
    references = write_evidence(directory, facts.items)
    report = build_team_report(
        facts,
        team,
        run_id=run_id,
        as_of=as_of,
        window=window,
        iteration_path=iteration_path,
        evidence_references=references,
        limitations=extra_limitations,
    )
    metrics = MetricSet(
        run_id=run_id, team_id=team.team_id, metrics=report.metrics, findings=report.findings
    )
    summary = build_summary(report, limit_bytes=resolved.config.output.summary_limit_bytes)
    markdown = render_markdown(report)

    hashes = {
        "facts.json": store.write_json(directory, "facts.json", facts.model_dump(mode="json")),
        "metrics.json": store.write_json(
            directory, "metrics.json", metrics.model_dump(mode="json")
        ),
        "report.json": store.write_json(directory, "report.json", report.model_dump(mode="json")),
        "summary.json": store.write_json(
            directory, "summary.json", summary.model_dump(mode="json")
        ),
    }
    store.write_text(directory, "report.md", markdown)

    partial = tuple(
        dict.fromkeys(
            (
                *facts.partial_sources,
                *(
                    f"metrica_parcial:{metric.id}"
                    for metric in report.metrics
                    if metric.status.value in ("partial", "unavailable")
                ),
            )
        )
    )
    state = RunState.PARTIAL if partial else RunState.COMPLETE
    run = store.finalize(
        directory,
        run_id=run_id,
        state=state,
        source_identity=source_identity(organization, team.project_id, team.team_id),
        collection_started_at=started_at,
        collection_finished_at=as_of,
        as_of=as_of,
        effective_config=resolved.effective,
        artifact_hashes=hashes,
        partial_reasons=partial,
        mcp_server_version=server_version,
        mcp_catalog_hash=catalog_hash,
    )
    exit_code = ExitCode.PARTIAL_CAPABILITY if partial else ExitCode.OK
    return RunOutcome(run=run, report=report, exit_code=exit_code, markdown=markdown)


def replay_run(
    store: RunStore,
    run_id: str,
    *,
    resolved: ResolvedConfig,
    team_alias: str | None = None,
) -> tuple[TeamReport, bool]:
    """Recalcula as métricas a partir dos fatos congelados e compara com o registrado.

    O resultado não depende do horário do replay: o instante de referência vem do manifesto.
    """
    run = store.load(run_id)
    stored_report = TeamReport.model_validate(run.artifact("report.json"))
    facts = FactSet.model_validate(run.artifact("facts.json"))
    alias = team_alias or stored_report.team_alias
    try:
        team = resolved.config.team(alias)
    except KeyError as error:
        raise ConfigError(
            "E_REPLAY_EQUIPE_AUSENTE",
            f"A equipe {alias!r} da execução não existe na configuração atual.",
            detail={"run_id": run_id, "team": alias},
            remediation="Use a configuração usada na coleta ou informe --team.",
        ) from error

    recomputed = build_team_report(
        facts,
        team,
        run_id=stored_report.run_id,
        as_of=datetime.fromisoformat(stored_report.as_of),
        window=stored_report.window,
        iteration_path=stored_report.iteration_path,
        evidence_references=stored_report.evidence_references,
        limitations=(),
    )
    identical = _comparable(recomputed) == _comparable(stored_report)
    return recomputed, identical


def _comparable(report: TeamReport) -> Mapping[str, Any]:
    """Compara apenas o que o replay deve reproduzir: métricas, pessoas e achados."""
    return {
        "metrics": [metric.model_dump(mode="json") for metric in report.metrics],
        "people": [row.model_dump(mode="json") for row in report.people],
        "findings": [finding.model_dump(mode="json") for finding in report.findings],
    }
