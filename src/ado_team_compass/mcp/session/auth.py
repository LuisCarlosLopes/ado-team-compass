"""Autorização do servidor MCP remoto oficial.

O transporte stdio recebe a credencial do ambiente do host e nada aqui se aplica a ele. Já o
servidor remoto oficial exige autorização própria, e ela é obtida pelo fluxo OAuth que o SDK
MCP implementa: descoberta, registro dinâmico do cliente, PKCE e renovação.

Invariante ZERO_SECRETS: nenhum valor de token entra na configuração do produto, em artefato
de execução ou em log. O material de autorização vive isolado em `~/.ado-team-compass/auth`,
com permissão restrita ao dono, e é o único lugar onde é gravado. O produto nunca pede senha
nem PAT: quem autentica é o provedor de identidade, no navegador do usuário.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ado_team_compass.errors import AccessError

__all__ = [
    "AUTHORIZATION_TIMEOUT_SECONDS",
    "CLIENT_NAME",
    "FileTokenStorage",
    "authorization_state",
    "forget_authorization",
    "interactive_auth",
    "silent_auth",
]

CLIENT_NAME = "ADO Team Compass"

#: Tempo máximo que o fluxo interativo espera pela autorização no navegador.
AUTHORIZATION_TIMEOUT_SECONDS = 300.0

_TOKEN_FILE_MODE = 0o600
_TOKEN_DIR_MODE = 0o700


def authorization_home() -> Path:
    """Diretório isolado do material de autorização, fora dos artefatos de execução."""
    override = os.environ.get("ADO_TEAM_COMPASS_AUTH_HOME")
    if override:
        return Path(override)
    return Path.home() / ".ado-team-compass" / "auth"


def _identity(server_url: str) -> str:
    """Nome de arquivo derivado da URL: não expõe organização no sistema de arquivos."""
    return hashlib.sha256(server_url.encode("utf-8")).hexdigest()[:32]


class FileTokenStorage:
    """Guarda tokens e registro do cliente em arquivo restrito ao dono.

    Implementa o protocolo `TokenStorage` do SDK. A escrita é atômica e o modo do arquivo é
    ajustado antes de qualquer conteúdo ser gravado, para que o material nunca exista em disco
    com permissão aberta.
    """

    def __init__(self, server_url: str, *, home: Path | None = None) -> None:
        self._home = home or authorization_home()
        self._path = self._home / f"{_identity(server_url)}.json"

    @property
    def path(self) -> Path:
        return self._path

    def _read(self) -> dict[str, Any]:
        if not self._path.is_file():
            return {}
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _write(self, payload: dict[str, Any]) -> None:
        self._home.mkdir(parents=True, exist_ok=True)
        self._home.chmod(_TOKEN_DIR_MODE)
        staging = self._path.with_suffix(".partial")
        # O descritor nasce com o modo restrito: o conteúdo nunca existe em disco aberto.
        descriptor = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, _TOKEN_FILE_MODE)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
        staging.replace(self._path)
        self._path.chmod(_TOKEN_FILE_MODE)

    async def get_tokens(self) -> Any:
        from mcp.shared.auth import OAuthToken

        stored = self._read().get("tokens")
        return OAuthToken.model_validate(stored) if stored else None

    async def set_tokens(self, tokens: Any) -> None:
        payload = self._read()
        payload["tokens"] = tokens.model_dump(mode="json", exclude_none=True)
        self._write(payload)

    async def get_client_info(self) -> Any:
        from mcp.shared.auth import OAuthClientInformationFull

        stored = self._read().get("client")
        return OAuthClientInformationFull.model_validate(stored) if stored else None

    async def set_client_info(self, client_info: Any) -> None:
        payload = self._read()
        payload["client"] = client_info.model_dump(mode="json", exclude_none=True)
        self._write(payload)

    def forget(self) -> bool:
        """Remove o material local. Não revoga nada no provedor de identidade."""
        if not self._path.is_file():
            return False
        self._path.unlink()
        return True

    def state(self) -> dict[str, Any]:
        """Estado auditável da autorização, sem nenhum valor de token."""
        payload = self._read()
        tokens = payload.get("tokens") or {}
        return {
            "stored": bool(tokens),
            "path": str(self._path),
            "has_refresh_token": bool(tokens.get("refresh_token")),
            "scope": tokens.get("scope"),
        }


class _CallbackReceiver:
    """Servidor mínimo em loopback que recebe o retorno da autorização.

    Só existe durante o fluxo interativo, escuta apenas em 127.0.0.1 e em porta efêmera, e
    encerra assim que o código chega. Nenhum valor recebido é registrado em log.
    """

    def __init__(self) -> None:
        from http.server import HTTPServer

        self._result: dict[str, str | None] = {}
        self._received = threading.Event()
        self._server = HTTPServer(("127.0.0.1", 0), self._handler_class())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        port: int = self._server.server_address[1]
        return port

    @property
    def redirect_uri(self) -> str:
        return f"http://127.0.0.1:{self.port}/callback"

    def _handler_class(self) -> Any:
        from http.server import BaseHTTPRequestHandler

        receiver = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                query = parse_qs(urlparse(self.path).query)
                receiver._result = {
                    name: next(iter(query.get(name, ())), None)
                    for name in ("code", "state", "error")
                }
                receiver._received.set()
                body = _CLOSING_PAGE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: Any) -> None:
                """Silencia o log da biblioteca padrão: a URL carrega o código de autorização."""

        return Handler

    def __enter__(self) -> _CallbackReceiver:
        self._thread.start()
        return self

    def __exit__(self, *_exception: object) -> None:
        self._server.shutdown()
        self._server.server_close()

    def wait(self, timeout: float) -> tuple[str, str | None]:
        if not self._received.wait(timeout):
            raise AccessError(
                "E_AUTORIZACAO_EXPIRADA",
                "A autorização não foi concluída no navegador dentro do tempo previsto.",
                remediation="Repita a autorização e conclua o login na janela aberta.",
            )
        failure = self._result.get("error")
        if failure:
            raise AccessError(
                "E_AUTORIZACAO_RECUSADA",
                f"O provedor de identidade recusou a autorização: {failure}.",
                remediation="Confirme que a sua conta tem acesso de leitura à organização.",
            )
        code = self._result.get("code")
        if not code:
            raise AccessError(
                "E_AUTORIZACAO_SEM_CODIGO",
                "O retorno da autorização não trouxe código.",
                remediation="Repita a autorização a partir do início.",
            )
        return code, self._result.get("state")


_CLOSING_PAGE = (
    "<!doctype html><html lang='pt-BR'><meta charset='utf-8'>"
    "<title>ADO Team Compass</title>"
    "<body style='font-family:system-ui;padding:3rem;max-width:32rem'>"
    "<h1>Autorização concluída</h1>"
    "<p>O ADO Team Compass recebeu a autorização de leitura. Pode fechar esta aba e voltar "
    "ao seu assistente.</p></body></html>"
)


def _client_metadata(redirect_uri: str) -> Any:
    from mcp.shared.auth import OAuthClientMetadata

    return OAuthClientMetadata(
        client_name=CLIENT_NAME,
        redirect_uris=[redirect_uri],
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        token_endpoint_auth_method="none",
    )


@contextmanager
def interactive_auth(server_url: str, *, home: Path | None = None) -> Iterator[Any]:
    """Provedor que conduz a autorização no navegador do usuário.

    Usado só pela entrada de login, que é um ato humano explícito. A coleta nunca abre
    navegador: ela usa `silent_auth` e falha com orientação quando não há autorização.
    """
    from mcp.client.auth import OAuthClientProvider

    storage = FileTokenStorage(server_url, home=home)
    with _CallbackReceiver() as receiver:

        async def redirect(authorization_url: str) -> None:
            import webbrowser

            opened = False
            if not os.environ.get("ADO_TEAM_COMPASS_NO_BROWSER"):
                opened = webbrowser.open(authorization_url)
            prefix = "Abra este endereço para autorizar" if not opened else "Autorize em"
            # Diagnóstico vai para stderr pelo chamador; aqui só devolvemos o endereço.
            _announce(f"{prefix}: {authorization_url}")

        async def callback() -> tuple[str, str | None]:
            from anyio.to_thread import run_sync

            return await run_sync(receiver.wait, AUTHORIZATION_TIMEOUT_SECONDS)

        yield OAuthClientProvider(
            server_url=server_url,
            client_metadata=_client_metadata(receiver.redirect_uri),
            storage=storage,
            redirect_handler=redirect,
            callback_handler=callback,
            timeout=AUTHORIZATION_TIMEOUT_SECONDS,
        )


def silent_auth(server_url: str, *, home: Path | None = None) -> Any:
    """Provedor que só reaproveita e renova autorização já concedida.

    Nenhuma coleta abre navegador nem bloqueia esperando por uma pessoa: sem autorização
    válida, o erro diz exatamente o que fazer.
    """
    from mcp.client.auth import OAuthClientProvider

    storage = FileTokenStorage(server_url, home=home)

    async def refuse(*_arguments: object) -> Any:
        raise AccessError(
            "E_AUTORIZACAO_AUSENTE",
            "Não há autorização válida para o servidor MCP remoto oficial.",
            detail={"server_url": server_url},
            remediation=(
                "Execute a entrada 'login' (ferramenta atc_login) para autorizar, ou "
                "configure o transporte stdio com 'setup --from-mcp-config'."
            ),
        )

    return OAuthClientProvider(
        server_url=server_url,
        client_metadata=_client_metadata("http://127.0.0.1:0/callback"),
        storage=storage,
        redirect_handler=refuse,
        callback_handler=refuse,
        timeout=AUTHORIZATION_TIMEOUT_SECONDS,
    )


def authorization_state(server_url: str, *, home: Path | None = None) -> dict[str, Any]:
    """Estado da autorização local, sem expor nenhum valor de token."""
    return FileTokenStorage(server_url, home=home).state()


def forget_authorization(server_url: str, *, home: Path | None = None) -> bool:
    """Apaga o material local de autorização. Não revoga nada no provedor de identidade."""
    return FileTokenStorage(server_url, home=home).forget()


def _announce(message: str) -> None:
    """Mensagem de fluxo interativo. Vai para stderr: stdout pode ser canal de protocolo."""
    import sys

    sys.stderr.write(f"ado-team-compass: {message}\n")
    sys.stderr.flush()
