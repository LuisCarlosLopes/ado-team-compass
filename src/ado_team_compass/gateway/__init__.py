"""API HTTPS autenticada de leitura para GPT Actions (T28, v0.3.1).

Este gateway serve **apenas relatórios já produzidos** pelo motor. Ele não fala com o Azure
DevOps, não dispara coleta e não executa nada: o coletor continua sendo o único componente
que usa o servidor MCP oficial. O token do GPT autoriza a API, nunca o Azure DevOps.
"""

from ado_team_compass.gateway.auth import (
    AccessControl,
    Principal,
    StaticTokenVerifier,
    TokenVerifier,
)
from ado_team_compass.gateway.store import ReportRepository

__all__ = [
    "AccessControl",
    "Principal",
    "ReportRepository",
    "StaticTokenVerifier",
    "TokenVerifier",
]
