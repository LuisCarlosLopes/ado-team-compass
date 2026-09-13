"""Exportação do schema OpenAPI consumido pelo GPT Actions (T28)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ado_team_compass.gateway.auth import AccessControl, StaticTokenVerifier
from ado_team_compass.gateway.store import ReportRepository
from ado_team_compass.runs import RunStore

__all__ = ["build_openapi", "export_openapi"]


def build_openapi(*, server_url: str = "https://compass.exemplo.interno") -> dict[str, Any]:
    """Gera o documento OpenAPI da API de leitura, sem depender de dados reais."""
    from ado_team_compass.gateway.app import create_app

    application = create_app(
        repository=ReportRepository(store=RunStore(Path())),
        verifier=StaticTokenVerifier(principals={}),
        access=AccessControl(path=Path("acl.json")),
    )
    document: dict[str, Any] = dict(application.openapi())
    document["servers"] = [
        {"url": server_url, "description": "Implantação dedicada por organização"}
    ]
    document["components"] = {
        **document.get("components", {}),
        "securitySchemes": {
            "oauth2": {
                "type": "oauth2",
                "description": (
                    "OAuth por usuário no provedor corporativo. O token autoriza somente esta "
                    "API; ele não dá acesso ao Azure DevOps."
                ),
                "flows": {
                    "authorizationCode": {
                        "authorizationUrl": f"{server_url}/oauth/authorize",
                        "tokenUrl": f"{server_url}/oauth/token",
                        "scopes": {"reports.read": "Ler relatórios das equipes autorizadas"},
                    }
                },
            }
        },
    }
    document["security"] = [{"oauth2": ["reports.read"]}]
    return document


def export_openapi(destination: Path, *, server_url: str | None = None) -> Path:
    """Grava o OpenAPI em disco para uso na configuração do GPT Actions."""
    document = build_openapi(
        **({"server_url": server_url} if server_url else {}),
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destination
