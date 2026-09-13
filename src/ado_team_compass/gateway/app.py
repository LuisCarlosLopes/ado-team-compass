"""Aplicação HTTP do gateway de leitura (T28).

Somente GET. Nenhuma rota dispara coleta, executa comando ou aceita URL arbitrária. Toda
consulta revalida a autorização no servidor, inclusive quando o cliente informa um run ID.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from ado_team_compass.gateway.auth import (
    AccessControl,
    AuthError,
    ForbiddenError,
    Principal,
    TokenVerifier,
)
from ado_team_compass.gateway.store import ReportRepository

__all__ = ["MAX_PAGE_SIZE", "create_app"]

#: Limite de itens por página nas listagens do gateway.
MAX_PAGE_SIZE = 100

_DISCLAIMER = (
    "Relatório já calculado pelo motor. O gateway não acessa o Azure DevOps e não atualiza "
    "dados: números vêm da execução indicada."
)


def create_app(
    *,
    repository: ReportRepository,
    verifier: TokenVerifier,
    access: AccessControl,
    clock: Callable[[], datetime] | None = None,
) -> Any:
    """Cria a aplicação FastAPI do gateway. O extra `api` precisa estar instalado."""
    try:
        from fastapi import Depends, FastAPI, Header, HTTPException, Query
        from fastapi.responses import JSONResponse
    except ImportError as error:  # pragma: no cover - extra opcional
        msg = "instale o extra 'api' para servir o gateway (fastapi e uvicorn)"
        raise RuntimeError(msg) from error

    now = clock or (lambda: datetime.now(UTC))

    application = FastAPI(
        title="ADO Team Compass — API de relatórios",
        version="0.3.1",
        description=(
            "Consulta somente leitura de relatórios já produzidos pelo ADO Team Compass. "
            "A coleta acontece fora desta API, exclusivamente pelo MCP oficial da Microsoft."
        ),
        openapi_tags=[{"name": "relatorios", "description": "Consultas autorizadas por equipe"}],
    )

    def principal_of(authorization: str | None = Header(default=None)) -> Principal:
        """Extrai e verifica o token; sem token válido, nada é servido."""
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="token ausente")
        try:
            return verifier.verify(authorization.split(" ", 1)[1].strip())
        except AuthError as error:
            raise HTTPException(status_code=401, detail=str(error)) from error

    def authorize(principal: Principal, team: str) -> None:
        try:
            access.require_team(principal, team)
        except ForbiddenError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error

    @application.get("/healthz", tags=["relatorios"])
    def healthz() -> dict[str, str]:
        """Verificação de vida. Não expõe dados de nenhuma equipe."""
        return {"status": "ok"}

    @application.get("/v1/teams", tags=["relatorios"])
    def list_teams(principal: Principal = Depends(principal_of)) -> dict[str, Any]:
        """Equipes que este usuário pode consultar."""
        allowed = set(access.teams_for(principal))
        available = [team for team in repository.teams() if team in allowed]
        return {"teams": available, "disclaimer": _DISCLAIMER}

    @application.get("/v1/teams/{team}/report", tags=["relatorios"])
    def latest_report(team: str, principal: Principal = Depends(principal_of)) -> dict[str, Any]:
        """Último relatório disponível da equipe autorizada."""
        authorize(principal, team)
        envelope = repository.latest(team, now=now())
        if envelope is None:
            raise HTTPException(
                status_code=404, detail=f"não há relatório disponível para a equipe {team!r}"
            )
        payload = envelope.as_dict()
        payload["disclaimer"] = _DISCLAIMER
        return payload

    @application.get("/v1/runs/{run_id}/report", tags=["relatorios"])
    def report_by_run(run_id: str, principal: Principal = Depends(principal_of)) -> dict[str, Any]:
        """Relatório de uma execução. O run ID não é autorização: a equipe é revalidada."""
        envelope = repository.by_run_id(run_id, now=now())
        if envelope is None:
            raise HTTPException(status_code=404, detail="execução não encontrada")
        authorize(principal, envelope.report.team_alias)
        payload = envelope.as_dict()
        payload["disclaimer"] = _DISCLAIMER
        return payload

    @application.get("/v1/runs/{run_id}/evidence", tags=["relatorios"])
    def evidence(
        run_id: str,
        reference: str | None = Query(default=None, max_length=32),
        limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE),
        cursor: int = Query(default=0, ge=0),
        principal: Principal = Depends(principal_of),
    ) -> dict[str, Any]:
        """Evidência minimizada de uma execução, paginada e sempre autorizada."""
        envelope = repository.by_run_id(run_id, now=now())
        if envelope is None:
            raise HTTPException(status_code=404, detail="execução não encontrada")
        authorize(principal, envelope.report.team_alias)

        if reference is not None:
            payload = repository.evidence(run_id, reference)
            if payload is None:
                raise HTTPException(status_code=404, detail="evidência não encontrada")
            return {"run_id": run_id, "reference": reference, "evidence": payload}

        references = sorted(envelope.report.evidence_references, key=int)
        page = references[cursor : cursor + limit]
        next_cursor = cursor + limit if cursor + limit < len(references) else None
        return {
            "run_id": run_id,
            "total": len(references),
            "limit": limit,
            "cursor": cursor,
            "next_cursor": next_cursor,
            "references": page,
        }

    @application.exception_handler(ForbiddenError)
    def forbidden_handler(_request: Any, error: ForbiddenError) -> Any:
        return JSONResponse(status_code=403, content={"detail": str(error)})

    return application
