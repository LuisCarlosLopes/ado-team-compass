"""Autorização do servidor remoto: fronteira, recusa acionável e ausência de segredo.

O fluxo completo é exercitado em `tests/integration/test_authorization_flow.py`. Aqui ficam o
recebimento do retorno em loopback, a fronteira entre transportes e as entradas da CLI.
"""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest

from ado_team_compass.cli import main
from ado_team_compass.contracts.config import ConnectionConfig, McpServerConfig, McpTransport
from ado_team_compass.errors import AccessError, ExitCode
from ado_team_compass.mcp.session.auth import FileTokenStorage, _CallbackReceiver
from ado_team_compass.mcp.session.official import default_auth

REMOTE = ConnectionConfig(
    alias="contoso",
    organization="contoso",
    server=McpServerConfig(transport=McpTransport.HTTP),
)
LOCAL = ConnectionConfig(
    alias="contoso",
    organization="contoso",
    server=McpServerConfig(
        transport=McpTransport.STDIO, command=("npx", "-y", "@azure-devops/mcp", "contoso")
    ),
)


def _visit(url: str) -> None:
    with httpx.Client(timeout=5) as client:
        client.get(url)


def test_the_loopback_receiver_only_listens_on_localhost():
    with _CallbackReceiver() as receiver:
        assert receiver.redirect_uri.startswith("http://127.0.0.1:")


def test_the_receiver_returns_the_code_and_state_it_received():
    with _CallbackReceiver() as receiver:
        threading.Thread(
            target=_visit, args=(f"{receiver.redirect_uri}?code=abc&state=xyz",), daemon=True
        ).start()
        assert receiver.wait(10) == ("abc", "xyz")


def test_a_refused_authorization_becomes_an_actionable_error():
    with _CallbackReceiver() as receiver:
        threading.Thread(
            target=_visit, args=(f"{receiver.redirect_uri}?error=access_denied",), daemon=True
        ).start()
        with pytest.raises(AccessError) as failure:
            receiver.wait(10)
    assert failure.value.code == "E_AUTORIZACAO_RECUSADA"
    assert failure.value.exit_code is ExitCode.ACCESS_DENIED


def test_a_return_without_code_is_refused():
    with _CallbackReceiver() as receiver:
        threading.Thread(target=_visit, args=(receiver.redirect_uri,), daemon=True).start()
        with pytest.raises(AccessError, match="não trouxe código"):
            receiver.wait(10)


def test_waiting_forever_is_not_an_option():
    with _CallbackReceiver() as receiver, pytest.raises(AccessError) as failure:
        receiver.wait(0.01)
    assert failure.value.code == "E_AUTORIZACAO_EXPIRADA"


def test_only_the_remote_transport_carries_authorization():
    """No stdio a credencial pertence ao ambiente do host: o produto nunca a vê."""
    assert default_auth(LOCAL) is None
    assert default_auth(REMOTE) is not None


def test_the_remote_transport_hands_the_authorization_to_the_http_client(monkeypatch):
    from contextlib import asynccontextmanager

    from ado_team_compass.mcp.session import official

    captured: dict[str, object] = {}

    @asynccontextmanager
    async def fake_client(url, timeout=None, auth=None):
        captured["url"] = url
        captured["auth"] = auth
        msg = "não conectamos: só verificamos o que seria enviado"
        raise RuntimeError(msg)
        yield  # pragma: no cover

    monkeypatch.setattr(
        "mcp.client.streamable_http.streamablehttp_client", fake_client, raising=False
    )
    transport = official.OfficialMcpTransport(REMOTE, auth="autorizacao-de-teste")
    # O SDK empacota a falha do canal em grupo de exceções: qualquer uma serve aqui.
    with pytest.raises(BaseException), transport:  # noqa: B017
        pass
    assert captured["auth"] == "autorizacao-de-teste"
    assert captured["url"] == "https://mcp.azuredevops.com/contoso/mcp"


def test_login_refuses_a_stdio_connection_with_an_explanation(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "config.yaml"
    config.write_text(_stdio_config(), encoding="utf-8")
    assert main(["login", f"--config={config}"]) == int(ExitCode.INVALID_INPUT)
    error = json.loads(capsys.readouterr().err)["error"]
    assert error["code"] == "E_AUTORIZACAO_NAO_SE_APLICA"
    assert "ambiente do host" in error["message"]


def test_login_without_configuration_asks_for_the_organization(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["login"]) == int(ExitCode.INVALID_INPUT)
    error = json.loads(capsys.readouterr().err)["error"]
    assert error["code"] == "E_SETUP_ORGANIZACAO_AUSENTE"


def test_logout_removes_the_local_material_and_says_it_does_not_revoke(
    tmp_path, capsys, monkeypatch
):
    home = tmp_path / "auth"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ADO_TEAM_COMPASS_AUTH_HOME", str(home))
    storage = FileTokenStorage("https://mcp.azuredevops.com/contoso/mcp", home=home)
    home.mkdir(parents=True)
    storage.path.write_text(json.dumps({"tokens": {"access_token": "x"}}), encoding="utf-8")

    assert main(["logout", "--organization=contoso"]) == int(ExitCode.OK)
    payload = json.loads(capsys.readouterr().out)
    assert payload["removed"] is True
    assert "provedor de identidade" in payload["note"]
    assert not storage.path.exists()


def test_doctor_reports_whether_authorization_exists_without_any_token_value(tmp_path, monkeypatch):
    from ado_team_compass.config import load_config
    from ado_team_compass.demo.dataset import CATALOG
    from ado_team_compass.demo.dataset import transport as synthetic_transport
    from ado_team_compass.diagnostics import diagnose

    monkeypatch.setenv("ADO_TEAM_COMPASS_AUTH_HOME", str(tmp_path / "auth"))

    @contextmanager
    def factory(_connection):
        yield synthetic_transport(tools=tuple(CATALOG))

    report, _ = diagnose(
        load_config(Path("examples/config/config.yaml")), transport_factory=factory
    )
    authorization = report["connections"][0]["authorization"]
    assert authorization["required"] is True
    assert authorization["stored"] is False
    assert "login" in authorization["note"]
    assert "access_token" not in json.dumps(report)


def _stdio_config() -> str:
    return """
schema_version: '1.0'
connections:
  - alias: contoso
    organization: contoso
    server:
      name: ado
      transport: stdio
      command: ["npx", "-y", "@azure-devops/mcp", "contoso"]
teams:
  - alias: plataforma
    connection: contoso
    project_id: produto
    team_id: plataforma
    profile: sprint_with_capacity
"""
