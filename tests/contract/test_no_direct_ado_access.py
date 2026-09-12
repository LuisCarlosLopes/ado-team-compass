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
    """Somente o pacote de sessão importa o SDK cliente MCP."""
    importers = [
        path
        for path in _product_files()
        if re.search(
            r"^\s*from\s+mcp[\s.]|^\s*import\s+mcp\b",
            path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
    ]
    assert {path.parent.name for path in importers} <= {"session"}
