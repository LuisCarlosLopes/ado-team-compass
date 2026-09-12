"""Entradas da CLI, opções comuns e mapeamento para códigos de saída.

Contrato: JSON vai para stdout; diagnóstico e erros vão para stderr. Nenhuma entrada
desta CLI acessa o Azure DevOps fora do MCP oficial.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from ado_team_compass import __version__
from ado_team_compass.errors import CompassError, ConfigError, ExitCode

__all__ = ["COMMANDS", "build_parser", "main"]

LOGGER = logging.getLogger("ado_team_compass")

Handler = Callable[[argparse.Namespace], ExitCode]


class _Command:
    """Descrição de uma entrada da CLI e a release que a torna disponível."""

    def __init__(self, name: str, help_text: str, release: str, handler: Handler | None) -> None:
        self.name = name
        self.help_text = help_text
        self.release = release
        self.handler = handler


def _not_implemented(command: _Command) -> Handler:
    def handler(_args: argparse.Namespace) -> ExitCode:
        raise ConfigError(
            "E_CMD_NAO_DISPONIVEL",
            f"A entrada '{command.name}' está planejada para a release {command.release} "
            "e ainda não foi implementada.",
            detail={"command": command.name, "release": command.release},
            remediation="Consulte o checklist de tarefas para o estado de implementação.",
        )

    return handler


def _handle_version(args: argparse.Namespace) -> ExitCode:
    payload = {"name": "ado-team-compass", "version": __version__}
    _emit(payload, args)
    return ExitCode.OK


def _emit(payload: dict[str, Any], args: argparse.Namespace) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    output: Path | None = getattr(args, "output", None)
    if output is None:
        sys.stdout.write(text + "\n")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
        LOGGER.info("Saída gravada em %s", output)


COMMANDS: tuple[_Command, ...] = (
    _Command("version", "Informa a versão do motor", "v0.1", _handle_version),
    _Command("setup", "Resolve organização, projetos, equipes e perfis", "v0.1", None),
    _Command("doctor", "Diagnostica ambiente, acesso, configuração e capacidades", "v0.1", None),
    _Command("collect", "Coleta apenas as fontes necessárias ao escopo e período", "v0.1", None),
    _Command("report", "Calcula e renderiza relatório de uma execução existente", "v0.1", None),
    _Command("status", "Atalho para coleta atual e relatório de equipe", "v0.1", None),
    _Command("allocation", "Visão de carga conhecida por pessoa/equipe", "v0.1", None),
    _Command("evidence", "Recupera evidência local por execução e referência", "v0.1", None),
    _Command("replay", "Recalcula métricas com entradas congeladas", "v0.1", None),
    _Command("demo", "Gera relatório com dados sintéticos, sem rede", "v0.1", None),
    _Command("render", "Gera o HTML operacional offline", "v0.1", None),
    _Command("decisions", "Exporta e importa decisões humanas", "v0.1", None),
    _Command("history", "Métricas históricas de compromisso e fluxo", "v0.2", None),
    _Command("planning", "Achados de regras de planejamento", "v0.2", None),
    _Command("run-scheduled", "Execução agendada não interativa", "v0.3", None),
    _Command("forecast", "Projeção experimental com premissas", "v0.4", None),
)


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, help="Caminho explícito da configuração")
    parser.add_argument("--team", help="Equipe por ID ou alias inequívoco")
    parser.add_argument("--period", help="Período da análise (ex.: iteração atual ou ISO)")
    parser.add_argument("--as-of", help="Instante de referência ISO-8601 do cálculo")
    parser.add_argument(
        "--format",
        choices=("json", "markdown", "html"),
        default="json",
        help="Formato da saída",
    )
    parser.add_argument("--output", type=Path, help="Arquivo de saída; padrão é stdout")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Proíbe qualquer chamada ao MCP e usa apenas dados locais",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Nunca solicita seleção; ambiguidade encerra com erro de configuração",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ado-team-compass",
        description="Visibilidade de entrega no Azure DevOps via MCP oficial da Microsoft.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Registra diagnóstico detalhado em stderr",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="entrada")
    for command in COMMANDS:
        sub = subparsers.add_parser(command.name, help=f"{command.help_text} ({command.release})")
        _add_common_options(sub)
        sub.set_defaults(_handler=command.handler or _not_implemented(command))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    if args.command is None:
        parser.print_help(sys.stderr)
        return int(ExitCode.INVALID_INPUT)
    handler: Handler = args._handler
    try:
        return int(handler(args))
    except CompassError as error:
        LOGGER.error("%s", error)
        sys.stderr.write(
            json.dumps({"error": error.as_dict()}, ensure_ascii=False, indent=2) + "\n"
        )
        return int(error.exit_code)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
