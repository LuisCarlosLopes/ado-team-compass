"""Fábrica da aplicação a partir do ambiente, usada pelo servidor ASGI (T28).

Nenhum valor padrão permissivo: sem emissor, audiência e JWKS configurados, a aplicação não
sobe. ACL ausente significa nenhum acesso, não acesso total.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ado_team_compass.gateway.app import create_app
from ado_team_compass.gateway.auth import AccessControl, OidcTokenVerifier
from ado_team_compass.gateway.store import ReportRepository
from ado_team_compass.runs import RunStore

__all__ = ["build_application"]


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        msg = f"variável de ambiente obrigatória ausente: {name}"
        raise RuntimeError(msg)
    return value


def build_application() -> Any:
    """Monta o gateway com verificação de token e ACL vindas do ambiente."""
    runs_dir = Path(_required("COMPASS_RUNS_DIR"))
    acl_file = Path(_required("COMPASS_ACL_FILE"))
    verifier = OidcTokenVerifier(
        issuer=_required("COMPASS_OIDC_ISSUER"),
        audience=_required("COMPASS_OIDC_AUDIENCE"),
        jwks_url=_required("COMPASS_OIDC_JWKS_URL"),
    )
    return create_app(
        repository=ReportRepository(store=RunStore(runs_dir)),
        verifier=verifier,
        access=AccessControl(path=acl_file),
    )


def __getattr__(name: str) -> Any:
    """`application` é construída sob demanda: importar o módulo não exige o ambiente.

    O servidor ASGI resolve `ado_team_compass.gateway.factory:application` no start-up.
    """
    if name == "application":
        return build_application()
    raise AttributeError(name)
