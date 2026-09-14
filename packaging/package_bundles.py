"""Empacota cada bundle com o motor necessário para instalação reproduzível (T15).

O pacote gerado contém as skills do host, o manifesto, o wheel do motor e o lock da release,
para que a instalação não dependa da árvore de desenvolvimento nem de resolução de versões no
momento da instalação. Nada aqui publica: a publicação é decisão de release.
"""

from __future__ import annotations

import argparse
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "integrations" / "shared"

__all__ = ["package_all", "package_bundle"]


def _hosts() -> Mapping[str, Any]:
    document = yaml.safe_load((SHARED / "hosts.yaml").read_text(encoding="utf-8"))
    return dict(document["hosts"])


def _install_notes(host: Mapping[str, Any], wheel_name: str, version: str) -> str:
    return f"""# Instalação — {host["display_name"]}

Versão do motor: {version}

1. Copie o conteúdo deste pacote para o diretório de plugins do host.
2. {str(host["registration_note"]).strip()}
3. {str(host["mcp_note"]).strip()}
4. Valide chamando a ferramenta `atc_doctor` e, sem credencial, `atc_demo`.

O motor acompanha o pacote em `engine/{wheel_name}` e o launcher `bin/atc-mcp.py` o prepara
sozinho na primeira execução, em um ambiente isolado sob `~/.ado-team-compass/runtime`. Não é
preciso instalar nada antes. Para preparar o ambiente você mesmo, ou para instalar o motor no
PATH e reaproveitá-lo em outros hosts:

   ```
   python -m pip install engine/{wheel_name}
   ```

Requisito: Python 3.11 ou superior acessível como `python3`. Para fixar outro interpretador,
aponte `ADO_TEAM_COMPASS_ENGINE_PYTHON` para ele; para proibir a preparação automática,
defina `ADO_TEAM_COMPASS_NO_BOOTSTRAP=1`.

## Atualização e remoção

Atualize substituindo os arquivos do bundle: o launcher passa a usar o ambiente da nova versão
do motor, e o anterior fica em `~/.ado-team-compass/runtime` até ser removido à mão. Execuções
já gravadas ficam fora do diretório do plugin (em `.ado-team-compass/`) e são preservadas na
atualização e na remoção. Para voltar à versão anterior, reinstale o pacote antigo: os
artefatos já gravados continuam legíveis enquanto a major do schema for a mesma.

Este pacote é somente leitura do Azure DevOps e não altera nenhum work item.
"""


def package_bundle(
    host_key: str,
    *,
    wheel: Path,
    lock: Path,
    version: str,
    output_dir: Path,
) -> Path:
    """Gera o zip de um host com bundle, wheel e lock."""
    host = _hosts()[host_key]
    bundle_dir = ROOT / str(host["bundle_dir"])
    if not bundle_dir.is_dir():
        msg = f"bundle ausente: {bundle_dir}; rode packaging/build_bundles.py"
        raise SystemExit(msg)
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"ado-team-compass-{host_key}-{version}.zip"

    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(bundle_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(bundle_dir).as_posix())
        archive.write(wheel, f"engine/{wheel.name}")
        archive.write(lock, "engine/uv.lock")
        archive.writestr("INSTALL.md", _install_notes(host, wheel.name, version))
    return destination


def package_all(*, wheel: Path, lock: Path, version: str, output_dir: Path) -> list[Path]:
    return [
        package_bundle(host_key, wheel=wheel, lock=lock, version=version, output_dir=output_dir)
        for host_key in sorted(_hosts())
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True, help="Wheel do motor")
    parser.add_argument("--lock", type=Path, default=ROOT / "uv.lock")
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist" / "bundles")
    arguments = parser.parse_args()
    for path in package_all(
        wheel=arguments.wheel,
        lock=arguments.lock,
        version=arguments.version,
        output_dir=arguments.output_dir,
    ):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
