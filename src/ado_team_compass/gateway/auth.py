"""Autenticação por usuário e ACL de equipes, com negativa por padrão (T28).

Regras:

- todo acesso exige token válido: emissor, audiência e expiração são verificados;
- a autorização é por equipe **no servidor**; equipe ou organização enviadas pelo modelo nunca
  autorizam nada;
- a ACL é lida a cada requisição, para que revogação e mudança valham na requisição seguinte;
- um run ID não é autorização: a equipe dona da execução é verificada de novo.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "AccessControl",
    "AuthError",
    "ForbiddenError",
    "OidcTokenVerifier",
    "Principal",
    "StaticTokenVerifier",
    "TokenVerifier",
]


class AuthError(Exception):
    """Token ausente, inválido ou expirado (401)."""


class ForbiddenError(Exception):
    """Token válido, mas sem acesso ao recurso pedido (403)."""


@dataclass(frozen=True)
class Principal:
    """Identidade autenticada. Nenhum dado sensível além do identificador do usuário."""

    subject: str
    issuer: str
    audience: str
    scopes: tuple[str, ...] = ()


@runtime_checkable
class TokenVerifier(Protocol):
    """Verificador de token. A implementação real valida assinatura, emissor e audiência."""

    def verify(self, token: str) -> Principal:
        """Devolve o principal ou levanta `AuthError`."""


@dataclass
class StaticTokenVerifier:
    """Verificador para testes e ambientes locais: mapa fixo de token para principal."""

    principals: Mapping[str, Principal] = field(default_factory=dict)

    def verify(self, token: str) -> Principal:
        principal = self.principals.get(token)
        if principal is None:
            raise AuthError("token desconhecido ou expirado")
        return principal


@dataclass
class OidcTokenVerifier:
    """Verificação de JWT com JWKS do provedor corporativo.

    Emissor, audiência, expiração e assinatura são obrigatórios. Nenhuma configuração
    desativa essas verificações.
    """

    issuer: str
    audience: str
    jwks_url: str
    algorithms: tuple[str, ...] = ("RS256",)
    leeway_seconds: int = 30

    def verify(self, token: str) -> Principal:
        try:
            import jwt
            from jwt import PyJWKClient
        except ImportError as error:  # pragma: no cover - extra opcional
            msg = "instale o extra 'api' para validar tokens (pyjwt[crypto])"
            raise AuthError(msg) from error

        try:
            signing_key = PyJWKClient(self.jwks_url).get_signing_key_from_jwt(token)
            claims: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=list(self.algorithms),
                audience=self.audience,
                issuer=self.issuer,
                leeway=self.leeway_seconds,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except Exception as error:
            raise AuthError("token inválido para este gateway") from error

        scope = claims.get("scope", "")
        scopes = tuple(scope.split()) if isinstance(scope, str) else ()
        return Principal(
            subject=str(claims["sub"]),
            issuer=str(claims["iss"]),
            audience=self.audience,
            scopes=scopes,
        )


@dataclass
class AccessControl:
    """ACL de equipes por usuário, relida a cada consulta.

    Formato do arquivo:

    ```json
    {"organization": "contoso", "users": {"user@empresa": ["equipe-a", "equipe-b"]}}
    ```
    """

    path: Path
    organization: str | None = None

    def _load(self) -> Mapping[str, Any]:
        if not self.path.is_file():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, Mapping) else {}

    def teams_for(self, principal: Principal) -> tuple[str, ...]:
        """Equipes autorizadas. Usuário desconhecido recebe lista vazia (negativa por padrão)."""
        document = self._load()
        users = document.get("users")
        if not isinstance(users, Mapping):
            return ()
        allowed = users.get(principal.subject)
        if not isinstance(allowed, Sequence) or isinstance(allowed, str | bytes):
            return ()
        return tuple(str(team) for team in allowed)

    def require_team(self, principal: Principal, team: str) -> None:
        """Autoriza uma equipe específica; qualquer outra resposta é 403."""
        if team not in self.teams_for(principal):
            msg = f"o usuário não tem acesso à equipe {team!r}"
            raise ForbiddenError(msg)
