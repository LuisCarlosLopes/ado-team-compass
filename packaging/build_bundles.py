"""Gera os bundles locais a partir da fonte compartilhada de instruções (T13, T26, T27).

Cada bundle é autocontido: as skills não referenciam arquivos fora do diretório instalado e
nenhuma variável ou sintaxe específica de um host aparece em outro. Fórmulas, contratos e
limites continuam no núcleo Python — aqui só entram invocação, manifesto e empacotamento.

Uso:
    python packaging/build_bundles.py            # grava os bundles
    python packaging/build_bundles.py --check    # falha se o que está versionado divergir
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "integrations" / "shared"
SKILLS = SHARED / "skills"
COMMON = SKILLS / "common.md"
LAUNCHER = SHARED / "launcher" / "atc-mcp.py"

#: Marcadores que jamais podem vazar de um host para outro.
FOREIGN_MARKERS = {
    "claude": ("ANTIGRAVITY_", "CODEX_", "CURSOR_", ".codex-plugin", ".cursor-plugin"),
    "antigravity": (
        "CLAUDE_PLUGIN_ROOT",
        "CODEX_",
        "CURSOR_",
        ".claude-plugin",
        ".codex-plugin",
        ".cursor-plugin",
    ),
    "codex": ("CLAUDE_PLUGIN_ROOT", "ANTIGRAVITY_", "CURSOR_", ".claude-plugin", ".cursor-plugin"),
    "cursor": (
        "CLAUDE_PLUGIN_ROOT",
        "ANTIGRAVITY_",
        "CODEX_",
        ".claude-plugin",
        ".codex-plugin",
    ),
}


def _version() -> str:
    text = (ROOT / "src" / "ado_team_compass" / "__init__.py").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("versão do motor não encontrada")


def _document() -> Mapping[str, Any]:
    parsed = yaml.safe_load((SHARED / "hosts.yaml").read_text(encoding="utf-8"))
    return dict(parsed)


def _hosts() -> Mapping[str, Any]:
    return dict(_document()["hosts"])


def mcp_server_entry(host: Mapping[str, Any], document: Mapping[str, Any]) -> dict[str, Any]:
    """Declaração do servidor MCP do motor para este host.

    O caminho usa a variável de raiz do plugin quando o host oferece uma; sem ela, a
    declaração não é gerada e o bundle documenta o registro manual.
    """
    launcher = str(document["launcher_path"])
    root = host.get("plugin_root")
    location = f"{root}/{launcher}" if root else launcher
    return {
        "command": "python3",
        "args": [location],
    }


def _skill_sources() -> list[Path]:
    return sorted(path for path in SKILLS.glob("*.md") if path != COMMON)


def render_skill(source: Path, host: Mapping[str, Any]) -> str:
    """Instrução compartilhada mais o rodapé específico do host."""
    body = source.read_text(encoding="utf-8").rstrip()
    common = COMMON.read_text(encoding="utf-8").strip()
    footer = (
        f"## Ambiente ({host['display_name']})\n\n"
        f"- {str(host['engine_note']).strip()}\n"
        f"- {str(host['mcp_note']).strip()}\n"
    )
    return f"{body}\n\n{common}\n\n{footer}"


def manifest(
    host_key: str, host: Mapping[str, Any], version: str, document: Mapping[str, Any]
) -> dict[str, Any]:
    # Manifesto mínimo CLI-safe (DECISÃO-002): schema estrito aceita apenas name e description.
    if host_key == "antigravity":
        return {
            "name": "ado-team-compass",
            "description": (
                "Visibilidade de entrega no Azure DevOps com cálculos auditáveis, "
                "exclusivamente pelo MCP oficial da Microsoft."
            ),
        }

    skills = [path.stem for path in _skill_sources()]
    base: dict[str, Any] = {
        "name": "ado-team-compass",
        "version": version,
        "description": (
            "Visibilidade de entrega no Azure DevOps com cálculos auditáveis, "
            "exclusivamente pelo MCP oficial da Microsoft."
        ),
        "author": {"name": "ADO Team Compass"},
        "keywords": ["azure-devops", "mcp", "sprint", "capacidade"],
        "skills": [f"./skills/{name}" for name in skills],
    }
    # Só declara o servidor quem oferece uma variável com a raiz do plugin: caminho relativo
    # dependeria do diretório de trabalho do host, que não é contrato de nenhum deles.
    if host.get("manifest_declares_mcp"):
        base["mcpServers"] = {
            str(document["server_name"]): mcp_server_entry(host, document),
        }
    if host_key == "claude":
        base["homepage"] = "https://github.com/LuisCarlosLopes/ado-team-compass"
    return base


def mcp_server_example(host: Mapping[str, Any], document: Mapping[str, Any]) -> str:
    """Entrada pronta para copiar na configuração de MCP de hosts sem raiz de plugin."""
    entry = mcp_server_entry(host, document)
    entry["args"] = [f"/caminho/absoluto/do/bundle/{document['launcher_path']}"]
    payload = {"mcpServers": {str(document["server_name"]): entry}}
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def build(*, check: bool) -> int:
    version = _version()
    document = _document()
    launcher = LAUNCHER.read_text(encoding="utf-8")
    divergent: list[str] = []
    valid_skill_stems = {source.stem for source in _skill_sources()}
    for host_key, host in _hosts().items():
        bundle = ROOT / str(host["bundle_dir"])
        skills_dir = bundle / str(host["skills_dir"])
        if skills_dir.is_dir():
            for skill_subdir in sorted(skills_dir.iterdir()):
                if skill_subdir.is_dir() and skill_subdir.name not in valid_skill_stems:
                    if check:
                        rel = skill_subdir.relative_to(ROOT)
                        divergent.append(f"diretório de skill órfão: {rel}")
                    else:
                        shutil.rmtree(skill_subdir)

        files: dict[Path, str] = {
            bundle / str(host["manifest_path"]): json.dumps(
                manifest(host_key, host, version, document),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        }
        for source in _skill_sources():
            destination = bundle / str(host["skills_dir"]) / source.stem / str(host["skill_file"])
            files[destination] = render_skill(source, host)
        files[bundle / "README.md"] = _bundle_readme(host, version)
        # O launcher acompanha todo bundle: é ele que o host sobe para falar com o motor.
        files[bundle / str(document["launcher_path"])] = launcher
        if not host.get("manifest_declares_mcp"):
            files[bundle / "mcp-server.json"] = mcp_server_example(host, document)

        for destination, content in files.items():
            for marker in FOREIGN_MARKERS[host_key]:
                if marker in content:
                    raise SystemExit(f"{destination}: marcador de outro host encontrado ({marker})")
            if check:
                current = destination.read_text(encoding="utf-8") if destination.is_file() else None
                if current != content:
                    divergent.append(str(destination.relative_to(ROOT)))
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")
            if destination.suffix == ".py":
                destination.chmod(0o755)

    if check and divergent:
        sys.stderr.write(
            "Bundles desatualizados; rode python packaging/build_bundles.py:\n- "
            + "\n- ".join(divergent)
            + "\n"
        )
        return 1
    return 0


def _bundle_readme(host: Mapping[str, Any], version: str) -> str:
    return f"""# ADO Team Compass — {host["display_name"]}

Bundle gerado a partir de `integrations/shared/`. Não edite os arquivos deste diretório: as
instruções compartilhadas vivem na fonte comum e os bundles são regenerados por
`python packaging/build_bundles.py`.

Versão do motor: {version}

## Instalação

1. Instale este bundle conforme o procedimento do {host["display_name"]}.
2. {str(host["registration_note"]).strip()}
3. {str(host["mcp_note"]).strip()}
4. Valide chamando a ferramenta `atc_doctor` e, sem credencial, `atc_demo`.

Não é preciso instalar a CLI antes. O motor acompanha o pacote de release em `engine/` e
`bin/atc-mcp.py` o prepara sozinho na primeira execução, em um ambiente isolado sob
`~/.ado-team-compass/runtime`. Quando o pacote `ado-team-compass` já estiver instalado na
máquina, é essa instalação que o launcher usa.

Requisito: Python 3.12 ou superior acessível como `python3`. Se o interpretador tiver outro
nome ou você quiser fixar um ambiente específico, aponte `ADO_TEAM_COMPASS_ENGINE_PYTHON` para
o interpretador desejado. Para proibir a preparação automática, defina
`ADO_TEAM_COMPASS_NO_BOOTSTRAP=1`.

## Limites

Somente leitura: nenhuma alteração é feita no Azure DevOps. Sem servidor MCP oficial
conectado, apenas `atc_demo`, `atc_replay`, `atc_report`, `atc_render` e `atc_evidence`
funcionam. Compatibilidade com esta versão do host precisa ser verificada em instalação real
antes de ser declarada.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verifica sem escrever; usado no CI")
    arguments = parser.parse_args()
    return build(check=arguments.check)


if __name__ == "__main__":
    raise SystemExit(main())
