"""Fluxo de autorização do servidor remoto oficial, ponta a ponta contra um servidor falso.

Nenhuma rede externa: o provedor de identidade é um servidor local que implementa descoberta,
registro dinâmico, autorização com PKCE e emissão de token. O que se prova aqui é o contrato —
que o produto obtém autorização sem pedir senha nem PAT, guarda o material fora dos artefatos
e reaproveita a concessão na chamada seguinte.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import anyio
import httpx
import pytest

from ado_team_compass.mcp.session.auth import (
    FileTokenStorage,
    authorization_state,
    forget_authorization,
    interactive_auth,
    silent_auth,
)

ACCESS_TOKEN = "token-de-teste-nao-e-segredo-real"
REFRESH_TOKEN = "refresh-de-teste"
GRANTED_CODE = "codigo-de-autorizacao"


class _FakeIdentityProvider:
    """Provedor de identidade mínimo, suficiente para exercitar o fluxo do SDK."""

    def __init__(self) -> None:
        self.issued_tokens = 0
        self.registrations = 0
        self.received_credentials: list[str] = []
        # Threading: o fluxo encadeia chamadas simultâneas (descoberta, autorização, token).
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        address = self._server.server_address
        return f"http://{address[0]!s}:{address[1]}"

    @property
    def resource_url(self) -> str:
        return f"{self.base_url}/mcp"

    def __enter__(self) -> _FakeIdentityProvider:
        self._thread.start()
        return self

    def __exit__(self, *_exception: object) -> None:
        self._server.shutdown()
        self._server.server_close()

    def _handler(self) -> Any:
        provider = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def _send(self, status: int, payload: Any = None, headers: Any = None) -> None:
                body = b"" if payload is None else json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                for name, value in (headers or {}).items():
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                path = urlparse(self.path).path
                base = provider.base_url
                if path.startswith("/.well-known/oauth-protected-resource"):
                    self._send(
                        200,
                        {"resource": provider.resource_url, "authorization_servers": [base]},
                    )
                elif path.startswith("/.well-known/oauth-authorization-server") or path.startswith(
                    "/.well-known/openid-configuration"
                ):
                    self._send(
                        200,
                        {
                            "issuer": base,
                            "authorization_endpoint": f"{base}/authorize",
                            "token_endpoint": f"{base}/token",
                            "registration_endpoint": f"{base}/register",
                            "response_types_supported": ["code"],
                            "grant_types_supported": ["authorization_code", "refresh_token"],
                            "code_challenge_methods_supported": ["S256"],
                        },
                    )
                elif path == "/authorize":
                    query = parse_qs(urlparse(self.path).query)
                    redirect = query["redirect_uri"][0]
                    state = query.get("state", [""])[0]
                    location = f"{redirect}?code={GRANTED_CODE}&state={state}"
                    self._send(302, None, {"Location": location})
                elif path == "/mcp":
                    authorization = self.headers.get("Authorization")
                    if authorization:
                        provider.received_credentials.append(authorization)
                        self._send(200, {"ok": True})
                    else:
                        self._send(
                            401,
                            {"error": "unauthorized"},
                            {
                                "WWW-Authenticate": (
                                    "Bearer resource_metadata="
                                    f'"{base}/.well-known/oauth-protected-resource/mcp"'
                                )
                            },
                        )
                else:
                    self._send(404, {"error": "not_found"})

            def do_POST(self) -> None:
                path = urlparse(self.path).path
                length = int(self.headers.get("Content-Length") or 0)
                self.rfile.read(length)
                if path == "/register":
                    provider.registrations += 1
                    self._send(
                        201,
                        {
                            "client_id": "cliente-de-teste",
                            "redirect_uris": ["http://127.0.0.1/callback"],
                            "token_endpoint_auth_method": "none",
                            "grant_types": ["authorization_code", "refresh_token"],
                            "response_types": ["code"],
                        },
                    )
                elif path == "/token":
                    provider.issued_tokens += 1
                    self._send(
                        200,
                        {
                            "access_token": ACCESS_TOKEN,
                            "token_type": "Bearer",
                            "expires_in": 3600,
                            "refresh_token": REFRESH_TOKEN,
                            "scope": "vso.work",
                        },
                    )
                else:
                    self._send(404, {"error": "not_found"})

            def log_message(self, format: str, *args: Any) -> None:
                """Silêncio: a URL de autorização carrega o código."""

        return Handler


@pytest.fixture
def identity() -> Iterator[_FakeIdentityProvider]:
    with _FakeIdentityProvider() as provider:
        yield provider


def _browser_simulator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Substitui o navegador: segue a URL de autorização até o retorno em loopback."""
    import webbrowser

    def open_url(url: str, *_args: object, **_kwargs: object) -> bool:
        with httpx.Client(follow_redirects=True, timeout=10) as client:
            client.get(url)
        return True

    monkeypatch.setattr(webbrowser, "open", open_url)


def test_login_obtains_authorization_without_asking_for_any_credential(
    identity, tmp_path, monkeypatch
):
    _browser_simulator(monkeypatch)
    home = tmp_path / "auth"

    async def scenario() -> httpx.Response:
        with interactive_auth(identity.resource_url, home=home) as provider:
            async with httpx.AsyncClient(auth=provider, timeout=10) as client:
                return await client.get(identity.resource_url)

    response = anyio.run(scenario)
    assert response.status_code == 200
    assert identity.issued_tokens == 1
    assert any(credential.startswith("Bearer ") for credential in identity.received_credentials)


def test_the_granted_authorization_is_reused_without_a_new_browser_round(
    identity, tmp_path, monkeypatch
):
    """A segunda chamada não passa pelo navegador: é o que torna a coleta não interativa."""
    _browser_simulator(monkeypatch)
    home = tmp_path / "auth"

    async def login() -> None:
        with interactive_auth(identity.resource_url, home=home) as provider:
            async with httpx.AsyncClient(auth=provider, timeout=10) as client:
                await client.get(identity.resource_url)

    async def collect() -> httpx.Response:
        provider = silent_auth(identity.resource_url, home=home)
        async with httpx.AsyncClient(auth=provider, timeout=10) as client:
            return await client.get(identity.resource_url)

    anyio.run(login)
    response = anyio.run(collect)
    assert response.status_code == 200


def test_the_material_never_lands_in_the_product_configuration_or_artifacts(
    identity, tmp_path, monkeypatch
):
    _browser_simulator(monkeypatch)
    home = tmp_path / "auth"

    async def scenario() -> None:
        with interactive_auth(identity.resource_url, home=home) as provider:
            async with httpx.AsyncClient(auth=provider, timeout=10) as client:
                await client.get(identity.resource_url)

    anyio.run(scenario)
    state = authorization_state(identity.resource_url, home=home)
    assert state["stored"] is True
    assert state["has_refresh_token"] is True
    assert ACCESS_TOKEN not in json.dumps(state)
    assert REFRESH_TOKEN not in json.dumps(state)
    # O material vive só no diretório isolado, nunca junto da configuração ou das execuções.
    stored = Path(state["path"])
    assert stored.parent == home
    assert ACCESS_TOKEN in stored.read_text(encoding="utf-8")


def test_logout_removes_the_local_material(identity, tmp_path, monkeypatch):
    _browser_simulator(monkeypatch)
    home = tmp_path / "auth"

    async def scenario() -> None:
        with interactive_auth(identity.resource_url, home=home) as provider:
            async with httpx.AsyncClient(auth=provider, timeout=10) as client:
                await client.get(identity.resource_url)

    anyio.run(scenario)
    assert forget_authorization(identity.resource_url, home=home) is True
    assert authorization_state(identity.resource_url, home=home)["stored"] is False
    assert forget_authorization(identity.resource_url, home=home) is False


def test_collection_never_opens_a_browser_and_says_what_to_do(identity, tmp_path):
    """Sem autorização concedida, a coleta falha com orientação em vez de travar."""
    from ado_team_compass.errors import AccessError

    home = tmp_path / "auth"

    async def scenario() -> None:
        provider = silent_auth(identity.resource_url, home=home)
        async with httpx.AsyncClient(auth=provider, timeout=10) as client:
            await client.get(identity.resource_url)

    with pytest.raises(AccessError) as failure:
        anyio.run(scenario)
    assert failure.value.code == "E_AUTORIZACAO_AUSENTE"
    assert "login" in (failure.value.remediation or "")


def test_the_storage_file_is_readable_only_by_its_owner(identity, tmp_path, monkeypatch):
    import os
    import stat

    _browser_simulator(monkeypatch)
    home = tmp_path / "auth"

    async def scenario() -> None:
        with interactive_auth(identity.resource_url, home=home) as provider:
            async with httpx.AsyncClient(auth=provider, timeout=10) as client:
                await client.get(identity.resource_url)

    anyio.run(scenario)
    path = FileTokenStorage(identity.resource_url, home=home).path
    assert path.is_file()
    # A escrita é atômica: nenhum resto parcial fica legível no diretório.
    assert not list(home.glob("*.partial"))
    if os.name == "nt":
        # O Windows não expressa permissão POSIX; lá o isolamento é o do perfil do usuário.
        pytest.skip("modo POSIX não se aplica a este sistema de arquivos")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(home.stat().st_mode) == 0o700
