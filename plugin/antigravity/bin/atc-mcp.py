#!/usr/bin/env python3
"""Sobe o servidor MCP do ADO Team Compass a partir do bundle instalado.

Este arquivo usa apenas a biblioteca padrão e existe para uma coisa: o host de IA subir o
motor sem que ninguém precise instalar a CLI antes. A ordem de resolução é conservadora —
um motor já instalado é sempre preferido a criar um ambiente novo.

1. `ADO_TEAM_COMPASS_ENGINE_PYTHON`, quando o operador indica o interpretador.
2. Motor já instalado neste interpretador ou no PATH.
3. Ambiente gerenciado em `~/.ado-team-compass/runtime/<versão>`, se já existir.
4. Wheel embutido no bundle, instalado uma única vez nesse ambiente gerenciado.

stdout é o canal do protocolo MCP: nada aqui escreve nele. Diagnóstico vai para stderr.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

#: Diretório do bundle instalado; o launcher vive em <bundle>/bin/.
BUNDLE = Path(__file__).resolve().parent.parent

#: Onde o wheel do motor é procurado, na ordem, dentro do bundle.
WHEEL_DIRECTORIES = ("engine", "bin")

MINIMUM_PYTHON = (3, 12)


def log(message: str) -> None:
    """Diagnóstico sempre em stderr: stdout pertence ao protocolo."""
    sys.stderr.write(f"ado-team-compass: {message}\n")
    sys.stderr.flush()


def runtime_home() -> Path:
    override = os.environ.get("ADO_TEAM_COMPASS_RUNTIME_HOME")
    if override:
        return Path(override)
    return Path.home() / ".ado-team-compass" / "runtime"


def venv_python(root: Path) -> Path:
    if os.name == "nt":
        return root / "Scripts" / "python.exe"
    return root / "bin" / "python"


def bundled_wheel() -> Path | None:
    """Wheel do motor embutido no pacote de release, quando presente."""
    for directory in WHEEL_DIRECTORIES:
        candidates = sorted((BUNDLE / directory).glob("ado_team_compass-*.whl"))
        if candidates:
            return candidates[-1]
    return None


def wheel_version(wheel: Path) -> str:
    parts = wheel.name.split("-")
    return parts[1] if len(parts) > 1 else "desconhecida"


def serves_engine(python: Path) -> bool:
    """Confirma que o interpretador enxerga o motor, sem importá-lo neste processo."""
    if not python.is_file():
        return False
    probe = subprocess.run(
        [str(python), "-c", "import ado_team_compass.server"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return probe.returncode == 0


def bootstrap(wheel: Path) -> Path:
    """Cria o ambiente gerenciado e instala o wheel embutido. Retorna o interpretador."""
    home = runtime_home()
    target = home / wheel_version(wheel)
    staging = home / f".building-{os.getpid()}"
    home.mkdir(parents=True, exist_ok=True)
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)

    log(f"preparando o motor {wheel_version(wheel)} em {target} (só na primeira execução)")
    try:
        # O ambiente é criado por subprocesso: em processo, o interpretador herda
        # __PYVENV_LAUNCHER__ no macOS e o ensurepip do ambiente novo aborta.
        creation = subprocess.run(
            [sys.executable, "-m", "venv", "--clear", str(staging)],
            stdout=sys.stderr,
            stderr=sys.stderr,
            check=False,
        )
        if creation.returncode != 0:
            shutil.rmtree(staging, ignore_errors=True)
            raise SystemExit(
                "Não foi possível criar o ambiente do motor. Instale-o uma vez com "
                f"'python3 -m pip install {wheel}' e reinicie o host."
            )
        install = subprocess.run(
            [
                str(venv_python(staging)),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
                "--quiet",
                str(wheel),
            ],
            stdout=sys.stderr,
            stderr=sys.stderr,
            check=False,
        )
        if install.returncode != 0:
            shutil.rmtree(staging, ignore_errors=True)
            raise SystemExit(
                "Falha ao instalar o motor embutido. Sem rede, instale-o uma vez com "
                f"'python3 -m pip install {wheel}' e reinicie o host."
            )
        try:
            staging.replace(target)
        except OSError:
            # Outro processo terminou o mesmo bootstrap primeiro: o ambiente dele vale.
            shutil.rmtree(staging, ignore_errors=True)
    except SystemExit:
        raise
    except Exception as failure:
        shutil.rmtree(staging, ignore_errors=True)
        raise SystemExit(f"Não foi possível preparar o motor: {failure}") from failure
    return venv_python(target)


def resolve() -> list[str]:
    """Comando que sobe o servidor MCP, na ordem de preferência documentada."""
    explicit = os.environ.get("ADO_TEAM_COMPASS_ENGINE_PYTHON")
    if explicit:
        return [explicit, "-m", "ado_team_compass.server"]

    if serves_engine(Path(sys.executable)):
        return [sys.executable, "-m", "ado_team_compass.server"]

    installed = shutil.which("ado-team-compass-mcp")
    if installed:
        return [installed]

    wheel = bundled_wheel()
    version = wheel_version(wheel) if wheel else None
    if version:
        managed = venv_python(runtime_home() / version)
        if serves_engine(managed):
            return [str(managed), "-m", "ado_team_compass.server"]

    if wheel is None:
        raise SystemExit(
            "Motor não encontrado e este bundle não traz o wheel embutido. Instale o pacote "
            "'ado-team-compass' no PATH ou use o pacote de release, que inclui engine/."
        )
    if os.environ.get("ADO_TEAM_COMPASS_NO_BOOTSTRAP"):
        raise SystemExit(
            "Motor não encontrado e o bootstrap está desabilitado por "
            "ADO_TEAM_COMPASS_NO_BOOTSTRAP. Instale o pacote 'ado-team-compass' no PATH."
        )
    return [str(bootstrap(wheel)), "-m", "ado_team_compass.server"]


def interpreter_version(python: str) -> tuple[int, ...]:
    """Versão do interpretador, perguntada a ele mesmo."""
    probe = subprocess.run(
        [python, "-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        return (0,)
    try:
        return tuple(int(part) for part in probe.stdout.strip().split("."))
    except ValueError:
        return (0,)


def compatible_interpreter() -> str | None:
    """Primeiro interpretador do PATH que atende à versão mínima.

    O `python3` do sistema costuma ser antigo — no macOS ainda é 3.9. Procurar por nome com
    versão evita que o host precise saber qual interpretador apontar.
    """
    for name in ("python3.14", "python3.13", "python3.12", "python3"):
        found = shutil.which(name)
        if found and interpreter_version(found) >= MINIMUM_PYTHON:
            return found
    return None


def main() -> int:
    required = ".".join(str(part) for part in MINIMUM_PYTHON)
    if sys.version_info < MINIMUM_PYTHON:
        # Já tentamos trocar de interpretador uma vez: insistir viraria laço.
        if os.environ.get("ADO_TEAM_COMPASS_LAUNCHER_REEXEC"):
            raise SystemExit(f"O motor exige Python {required} ou superior.")
        newer = compatible_interpreter()
        if newer is None:
            raise SystemExit(
                f"O motor exige Python {required} ou superior, e este host subiu o launcher "
                f"com {sys.version_info[0]}.{sys.version_info[1]}. Instale um "
                "interpretador compatível ou aponte ADO_TEAM_COMPASS_ENGINE_PYTHON para ele."
            )
        log(f"trocando para {newer}: este interpretador é anterior a {required}")
        os.environ["ADO_TEAM_COMPASS_LAUNCHER_REEXEC"] = "1"
        os.execv(newer, [newer, str(Path(__file__).resolve()), *sys.argv[1:]])
    command = [*resolve(), *sys.argv[1:]]
    if os.name == "nt":
        return subprocess.run(command, check=False).returncode
    os.execv(command[0], command)
    return 0  # pragma: no cover - inalcançável após execv


if __name__ == "__main__":
    raise SystemExit(main())
