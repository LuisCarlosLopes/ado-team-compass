"""T03/V33 — o produto não possui nenhum canal direto ao Azure DevOps.

Varredura estática do código de produto: nenhum endpoint REST/OData/Analytics, nenhum SDK
do Azure DevOps, nenhuma CLI de consulta e nenhum cliente HTTP próprio. O único canal é o
servidor MCP oficial, alcançado pelo SDK cliente MCP.
"""

import re
from pathlib import Path

import pytest

SOURCE = Path("src/ado_team_compass")

# A negativa vive em contracts/config.py: é lá que os hosts diretos são recusados.
DENYLIST_OWNER = SOURCE / "contracts" / "config.py"

FORBIDDEN_PATTERNS = {
    "endpoint REST do ADO": re.compile(r"dev\.azure\.com", re.IGNORECASE),
    "host legado do ADO": re.compile(r"visualstudio\.com", re.IGNORECASE),
    "caminho de API REST": re.compile(r"_apis/"),
    "consulta OData/Analytics": re.compile(r"\bodata\b", re.IGNORECASE),
    "SDK do Azure DevOps": re.compile(r"\bazure\.devops\b|vsts\.|azure-devops-python-api"),
    "CLI de consulta ao ADO": re.compile(r"\baz\s+(boards|devops|pipelines)\b"),
    "cliente HTTP próprio": re.compile(r"^\s*import\s+(requests|httpx)\b", re.MULTILINE),
}


# Uma ocorrência é aceita somente quando a própria linha declara a proibição — o que
# distingue documentação da restrição de uma chamada real.
REFUSAL = re.compile(r"nenhum|não|nunca|proib|recus|denylist|DIRECT_ADO", re.IGNORECASE)


def _product_files() -> list[Path]:
    return sorted(path for path in SOURCE.rglob("*.py"))


def test_product_has_source_files_to_scan():
    assert len(_product_files()) > 10


@pytest.mark.parametrize("description", sorted(FORBIDDEN_PATTERNS))
def test_no_direct_azure_devops_channel_in_product_code(description):
    pattern = FORBIDDEN_PATTERNS[description]
    offenders = []
    for path in _product_files():
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            if path == DENYLIST_OWNER:
                continue
            line_number = text[: match.start()].count("\n") + 1
            line = text.splitlines()[line_number - 1]
            if REFUSAL.search(line):
                continue
            offenders.append(f"{path}:{line_number}")
    assert not offenders, f"{description} encontrado em: {', '.join(offenders)}"


def test_direct_hosts_appear_only_as_a_refusal_list():
    text = DENYLIST_OWNER.read_text(encoding="utf-8")
    assert "DIRECT_ADO_HOSTS" in text
    assert "nunca são endpoint de MCP" in text


def test_only_the_official_mcp_remote_url_template_is_used():
    from ado_team_compass.contracts.config import OFFICIAL_REMOTE_URL_TEMPLATE

    assert OFFICIAL_REMOTE_URL_TEMPLATE == "https://mcp.azuredevops.com/{organization}/mcp"


def test_every_transport_call_goes_through_the_mcp_session_package():
    """Somente o pacote de sessão importa o SDK **cliente** MCP.

    O motor também é servidor MCP para o host de IA, e esse é outro papel: o SDK de servidor
    pertence a `server/` e nunca abre canal para o Azure DevOps.
    """
    client_import = re.compile(
        r"^\s*from\s+mcp\.client[\s.]|^\s*import\s+mcp\.client\b", re.MULTILINE
    )
    importers = [
        path for path in _product_files() if client_import.search(path.read_text(encoding="utf-8"))
    ]
    assert importers, "o cliente MCP precisa ser importado em algum lugar"
    assert {path.parent.name for path in importers} <= {"session"}


def test_the_mcp_server_package_never_opens_a_client_session():
    """O servidor exposto ao host não fala com o Azure DevOps: ele executa o motor local."""
    server_files = sorted((SOURCE / "server").rglob("*.py"))
    assert server_files, "o pacote do servidor MCP precisa existir"
    for path in server_files:
        text = path.read_text(encoding="utf-8")
        assert "mcp.client" not in text, f"{path} importa o SDK cliente"
        assert "ClientSession" not in text, f"{path} abre sessão de cliente"


def test_only_the_session_and_server_packages_touch_the_mcp_sdk():
    """Qualquer uso do SDK MCP fica confinado aos dois pacotes de fronteira."""
    any_import = re.compile(r"^\s*from\s+mcp[\s.]|^\s*import\s+mcp\b", re.MULTILINE)
    importers = [
        path for path in _product_files() if any_import.search(path.read_text(encoding="utf-8"))
    ]
    assert {path.parent.name for path in importers} <= {"session", "server"}
