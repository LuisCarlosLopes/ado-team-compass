"""Execução agendada não interativa (T23, T24).

Propriedades garantidas:

- idempotência por chave (configuração, equipe, janela e dia): repetir a execução não
  duplica resultado;
- exclusão mútua por lock: duas execuções simultâneas não produzem dois resultados;
- um sucesso anterior nunca é substituído por relatório vazio quando a execução falha;
- nada é enviado a lugar nenhum: notificação é template, não ação.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ado_team_compass.adapters.ado_mcp import AdoMcpClient
from ado_team_compass.config.loader import ResolvedConfig
from ado_team_compass.contracts.config import TeamConfig
from ado_team_compass.errors import CompassError, ExitCode
from ado_team_compass.pipeline import RunOutcome, execute_status
from ado_team_compass.runs import RunStore
from ado_team_compass.runs.lock import (
    ScheduleKey,
    SuccessMarker,
    acquire_lock,
    read_marker,
    write_marker,
)
from ado_team_compass.runs.store import hash_payload

__all__ = ["ScheduledResult", "run_scheduled", "schedule_key_for"]


@dataclass(frozen=True)
class ScheduledResult:
    """Resultado de uma execução agendada, incluindo o caso 'já executada'."""

    key: ScheduleKey
    status: str
    run_id: str | None
    exit_code: ExitCode
    outcome: RunOutcome | None = None
    previous_run_id: str | None = None
    error: CompassError | None = None
    notification: dict[str, Any] | None = None


def schedule_key_for(
    resolved: ResolvedConfig, team: TeamConfig, *, as_of: datetime, window: str | None
) -> ScheduleKey:
    """Chave estável: muda com a configuração efetiva, a equipe, a janela e o dia."""
    return ScheduleKey(
        config_hash=hash_payload(resolved.effective)[:16],
        team_alias=team.alias,
        window=window or "janela-corrente",
        day=as_of.date().isoformat(),
    )


def run_scheduled(
    client: AdoMcpClient,
    team: TeamConfig,
    *,
    organization: str,
    as_of: datetime,
    store: RunStore,
    resolved: ResolvedConfig,
    state_root: Path,
    window: str | None = None,
    force: bool = False,
    include_history: bool = False,
) -> ScheduledResult:
    """Executa uma coleta agendada sob lock, respeitando o marcador de sucesso."""
    key = schedule_key_for(resolved, team, as_of=as_of, window=window)
    existing = read_marker(state_root, key)
    if existing is not None and not force:
        return ScheduledResult(
            key=key,
            status="ja_executada",
            run_id=existing.run_id,
            exit_code=ExitCode.OK,
            previous_run_id=existing.run_id,
        )

    with acquire_lock(state_root, key, now=as_of):
        # Outra execução pode ter concluído enquanto esperávamos pelo lock.
        confirmed = read_marker(state_root, key)
        if confirmed is not None and not force:
            return ScheduledResult(
                key=key,
                status="ja_executada",
                run_id=confirmed.run_id,
                exit_code=ExitCode.OK,
                previous_run_id=confirmed.run_id,
            )
        try:
            outcome = execute_status(
                client,
                team,
                organization=organization,
                as_of=as_of,
                store=store,
                resolved=resolved,
                iteration_path=window,
                include_history=include_history,
            )
        except CompassError as error:
            previous = existing.run_id if existing else None
            return ScheduledResult(
                key=key,
                status="falha",
                run_id=None,
                exit_code=error.exit_code,
                previous_run_id=previous,
                error=error,
                notification=_notification_template(
                    team=team,
                    title=f"Falha na coleta agendada da equipe {team.alias}",
                    body=(
                        f"{error.code}: {error.message} "
                        f"Ação sugerida: {error.remediation or 'verificar diagnóstico'}. "
                        + (
                            f"O último relatório válido continua sendo {previous}."
                            if previous
                            else "Não há relatório válido anterior para esta chave."
                        )
                    ),
                    actionable=True,
                ),
            )

        write_marker(
            state_root,
            key,
            SuccessMarker(
                key=key.digest(),
                run_id=outcome.run.manifest.run_id,
                finished_at=as_of,
                state=outcome.run.manifest.state.value,
            ),
        )
        notification = None
        if _is_relevant_change(outcome, existing):
            notification = _notification_template(
                team=team,
                title=f"Relatório atualizado da equipe {team.alias}",
                body=(
                    f"Execução {outcome.run.manifest.run_id} concluída com estado "
                    f"{outcome.run.manifest.state.value}."
                ),
                actionable=False,
            )
        return ScheduledResult(
            key=key,
            status="executada",
            run_id=outcome.run.manifest.run_id,
            exit_code=outcome.exit_code,
            outcome=outcome,
            previous_run_id=existing.run_id if existing else None,
            notification=notification,
        )


def _is_relevant_change(outcome: RunOutcome, previous: SuccessMarker | None) -> bool:
    """Notificação só em mudança relevante ou falha acionável."""
    if previous is None:
        return True
    return previous.state != outcome.run.manifest.state.value


def _notification_template(
    *, team: TeamConfig, title: str, body: str, actionable: bool
) -> dict[str, Any]:
    """Template de notificação. Publicar é ação futura separada, com canal autorizado."""
    return {
        "team": team.alias,
        "title": title,
        "body": body,
        "actionable": actionable,
        "delivery": "template: nenhum canal é acionado por esta execução",
    }
