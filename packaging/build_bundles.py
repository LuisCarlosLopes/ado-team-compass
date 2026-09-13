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
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "integrations" / "shared"
SKILLS = SHARED / "skills"
COMMON = SKILLS / "common.md"

#: Marcadores que jamais podem vazar de um host para outro.
FOREIGN_MARKERS = {
    "claude": ("ANTIGRAVITY_", "CODEX_", ".codex-plugin"),
    "antigravity": ("CLAUDE_PLUGIN_ROOT", "CODEX_", ".claude-plugin", ".codex-plugin"),
    "codex": ("CLAUDE_PLUGIN_ROOT", "ANTIGRAVITY_", ".claude-plugin"),
}


def _version() -> str:
    text = (ROOT / "src" / "ado_team_compass" / "__init__.py").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("versão do motor não encontrada")


def _hosts() -> Mapping[str, Any]:
    document = yaml.safe_load((SHARED / "hosts.yaml").read_text(encoding="utf-8"))
    return dict(document["hosts"])


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


def manifest(host_key: str, host: Mapping[str, Any], version: str) -> dict[str, Any]:
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
        "requirements": {
            "engine": "ado-team-compass",
            "engine_version": version,
            "mcp_server": "azure-devops (oficial Microsoft)",
        },
    }
    if host_key == "claude":
        base["homepage"] = "https://github.com/LuisCarlosLopes/ado-team-compass"
    return base


def build(*, check: bool) -> int:
    version = _version()
    divergent: list[str] = []
    for host_key, host in _hosts().items():
        bundle = ROOT / str(host["bundle_dir"])
        files: dict[Path, str] = {
            bundle / str(host["manifest_path"]): json.dumps(
                manifest(host_key, host, version), ensure_ascii=False, indent=2, sort_keys=True
            )
            + "\n"
        }
        for source in _skill_sources():
            destination = bundle / str(host["skills_dir"]) / source.stem / str(host["skill_file"])
            files[destination] = render_skill(source, host)
        files[bundle / "README.md"] = _bundle_readme(host, version)

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

## Instalação

1. Instale o motor no ambiente do usuário:

   ```
   pip install ado-team-compass=={version}
   ```

2. {str(host["mcp_note"]).strip()}
3. Instale este bundle conforme o procedimento do {host["display_name"]}.
4. Valide com `ado-team-compass doctor` e, sem credencial, com `ado-team-compass demo`.

## Limites

Somente leitura: nenhuma alteração é feita no Azure DevOps. Sem servidor MCP oficial
conectado, apenas `demo`, `replay`, `report`, `render` e `evidence` funcionam. Compatibilidade
com esta versão do host precisa ser verificada em instalação real antes de ser declarada.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verifica sem escrever; usado no CI")
    arguments = parser.parse_args()
    return build(check=arguments.check)


if __name__ == "__main__":
    raise SystemExit(main())
