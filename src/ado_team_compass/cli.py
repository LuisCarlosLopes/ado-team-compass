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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ado_team_compass import __version__
from ado_team_compass.config.loader import ResolvedConfig, load_config
from ado_team_compass.contracts.config import (
    ConnectionConfig,
    McpServerConfig,
    McpTransport,
    TeamConfig,
)
from ado_team_compass.contracts.report import TeamReport
from ado_team_compass.diagnostics import TransportFactory, diagnose
from ado_team_compass.errors import CompassError, ConfigError, ExitCode
from ado_team_compass.pipeline import RunOutcome, execute_status, replay_run
from ado_team_compass.reporting import render_markdown
from ado_team_compass.runs import RunStore

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


DEFAULT_CONFIG_PATH = Path(".ado-team-compass/config.yaml")

#: Instante fixo da demonstração: o relatório sintético é reproduzível.
DEMO_AS_OF = datetime.fromisoformat("2026-09-15T12:00:00-03:00")


def _config_path(args: argparse.Namespace) -> Path:
    explicit: Path | None = getattr(args, "config", None)
    if explicit is not None:
        return explicit
    from os import environ

    from_env = environ.get("ADO_TEAM_COMPASS_CONFIG")
    return Path(from_env) if from_env else DEFAULT_CONFIG_PATH


def _load_optional_config(args: argparse.Namespace) -> ResolvedConfig | None:
    """Carrega a configuração quando existir; ausência é diagnóstico, não exceção."""
    path = _config_path(args)
    if not path.is_file():
        if getattr(args, "config", None) is not None:
            # Caminho explícito inexistente é erro de entrada.
            load_config(path)
        return None
    return load_config(path)


def _resolve_as_of(args: argparse.Namespace) -> datetime:
    """Instante de referência explícito; sem ele, o relógio é lido uma única vez aqui."""
    raw: str | None = getattr(args, "as_of", None)
    if raw is None:
        return datetime.now(UTC)
    try:
        moment = datetime.fromisoformat(raw)
    except ValueError as error:
        raise ConfigError(
            "E_ENTRADA_AS_OF_INVALIDA",
            f"O instante de referência {raw!r} não é ISO-8601 válido.",
            detail={"as_of": raw},
            remediation="Use, por exemplo, 2026-09-15T12:00:00-03:00.",
        ) from error
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _require_config(args: argparse.Namespace) -> ResolvedConfig:
    resolved = _load_optional_config(args)
    if resolved is None:
        raise ConfigError(
            "E_CFG_AUSENTE",
            "Nenhuma configuração foi encontrada para esta execução.",
            remediation="Execute 'setup' ou informe --config.",
        )
    return resolved


def _select_team(resolved: ResolvedConfig, args: argparse.Namespace) -> TeamConfig:
    """Seleção inequívoca: sem equipe definida, execução não interativa é erro."""
    selector: str | None = getattr(args, "team", None)
    if selector is not None:
        try:
            return resolved.config.team(selector)
        except KeyError as error:
            raise ConfigError(
                "E_EQUIPE_DESCONHECIDA",
                f"A equipe {selector!r} não existe na configuração.",
                detail={"team": selector, "available": [t.alias for t in resolved.config.teams]},
                remediation="Use um alias ou ID da lista de equipes configuradas.",
            ) from error
    if len(resolved.config.teams) == 1:
        return resolved.config.teams[0]
    raise ConfigError(
        "E_EQUIPE_AMBIGUA",
        "A configuração tem mais de uma equipe e nenhuma foi selecionada.",
        detail={"available": [team.alias for team in resolved.config.teams]},
        remediation="Informe --team com o alias ou o ID da equipe; nenhuma é escolhida por padrão.",
    )


def _store_for(resolved: ResolvedConfig) -> RunStore:
    return RunStore(Path(resolved.config.output.directory))


def _emit_outcome(outcome: RunOutcome, args: argparse.Namespace) -> ExitCode:
    if args.format == "markdown":
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(outcome.markdown, encoding="utf-8")
        else:
            sys.stdout.write(outcome.markdown)
    else:
        _emit(
            {
                "run_id": outcome.run.manifest.run_id,
                "state": outcome.run.manifest.state.value,
                "run_directory": str(outcome.run.directory),
                "report": outcome.report.model_dump(mode="json"),
            },
            args,
        )
    LOGGER.info("Execução %s gravada em %s", outcome.run.manifest.run_id, outcome.run.directory)
    return outcome.exit_code


def _run_collection(args: argparse.Namespace, *, transport_factory: Any = None) -> RunOutcome:
    from ado_team_compass.adapters.ado_mcp import AdoMcpClient
    from ado_team_compass.mcp.session.official import official_transport

    resolved = _require_config(args)
    team = _select_team(resolved, args)
    connection = next(
        connection
        for connection in resolved.config.connections
        if connection.alias == team.connection
    )
    if args.offline:
        raise ConfigError(
            "E_COLETA_OFFLINE",
            "A coleta exige o servidor MCP oficial conectado.",
            remediation="Use 'demo', 'replay' ou 'report' sobre uma execução já coletada.",
        )
    factory = transport_factory or getattr(args, "_transport_factory", None) or official_transport
    as_of = _resolve_as_of(args)
    with factory(connection) as transport:
        client = AdoMcpClient(transport=transport)
        client.handshake()
        return execute_status(
            client,
            team,
            organization=connection.organization,
            as_of=as_of,
            store=_store_for(resolved),
            resolved=resolved,
            iteration_path=getattr(args, "period", None),
        )


def _handle_status(args: argparse.Namespace) -> ExitCode:
    return _emit_outcome(_run_collection(args), args)


def _handle_collect(args: argparse.Namespace) -> ExitCode:
    outcome = _run_collection(args)
    _emit(
        {
            "run_id": outcome.run.manifest.run_id,
            "state": outcome.run.manifest.state.value,
            "run_directory": str(outcome.run.directory),
            "partial_reasons": list(outcome.run.manifest.partial_reasons),
            "items": len(outcome.report.evidence_references),
        },
        args,
    )
    return outcome.exit_code


def _handle_demo(args: argparse.Namespace) -> ExitCode:
    """Relatório completo com dados sintéticos: sem credencial e sem rede."""
    from ado_team_compass.adapters.ado_mcp import AdoMcpClient
    from ado_team_compass.config import resolve_config
    from ado_team_compass.demo import ORGANIZATION, demo_config_document, transport

    resolved = resolve_config(demo_config_document())
    team = resolved.config.teams[0]
    as_of = _resolve_as_of(args) if getattr(args, "as_of", None) else DEMO_AS_OF
    directory = args.output or Path(".ado-team-compass/demo")
    store = RunStore(directory)
    client = AdoMcpClient(transport=transport())
    client.handshake()
    outcome = execute_status(
        client,
        team,
        organization=ORGANIZATION,
        as_of=as_of,
        store=store,
        resolved=resolved,
    )
    if args.format == "markdown":
        sys.stdout.write(outcome.markdown)
    else:
        sys.stdout.write(
            json.dumps(
                {
                    "run_id": outcome.run.manifest.run_id,
                    "run_directory": str(outcome.run.directory),
                    "report": outcome.report.model_dump(mode="json"),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                default=str,
            )
            + "\n"
        )
    return outcome.exit_code


def _handle_report(args: argparse.Namespace) -> ExitCode:
    """Renderiza uma execução já persistida, sem nova leitura do MCP."""
    resolved = _require_config(args)
    store = _store_for(resolved)
    run_id = getattr(args, "run", None)
    run = store.load(run_id) if run_id else None
    if run is None:
        team = _select_team(resolved, args)
        run = store.latest(team.alias)
    if run is None:
        raise ConfigError(
            "E_RUN_INEXISTENTE",
            "Não há execução persistida para renderizar.",
            remediation="Execute 'status' ou 'collect' antes de 'report'.",
        )
    report = TeamReport.model_validate(run.artifact("report.json"))
    if args.format == "markdown":
        sys.stdout.write(render_markdown(report))
        return ExitCode.OK
    _emit(report.model_dump(mode="json"), args)
    return ExitCode.PARTIAL_CAPABILITY if run.manifest.state.value != "complete" else ExitCode.OK


def _handle_allocation(args: argparse.Namespace) -> ExitCode:
    """Carga conhecida por pessoa da execução mais recente."""
    resolved = _require_config(args)
    store = _store_for(resolved)
    team = _select_team(resolved, args)
    run = store.load(args.run) if getattr(args, "run", None) else store.latest(team.alias)
    if run is None:
        raise ConfigError(
            "E_RUN_INEXISTENTE",
            "Não há execução persistida para esta equipe.",
            remediation="Execute 'status' antes de 'allocation'.",
        )
    report = TeamReport.model_validate(run.artifact("report.json"))
    _emit(
        {
            "run_id": report.run_id,
            "unit": report.unit,
            "window": report.window.model_dump(mode="json") if report.window else None,
            "people": [row.model_dump(mode="json") for row in report.people],
            "limitations": list(report.limitations),
        },
        args,
    )
    return ExitCode.OK


def _handle_evidence(args: argparse.Namespace) -> ExitCode:
    """Recupera evidência local por execução e referência, sem nova leitura do ADO."""
    resolved = _require_config(args)
    store = _store_for(resolved)
    run_id = getattr(args, "run", None)
    if run_id is None:
        team = _select_team(resolved, args)
        run = store.latest(team.alias)
        if run is None:
            raise ConfigError(
                "E_RUN_INEXISTENTE",
                "Não há execução persistida para consultar evidência.",
                remediation="Execute 'status' antes de 'evidence'.",
            )
    else:
        run = store.load(run_id)
    reference: str | None = getattr(args, "reference", None)
    if reference is None:
        _emit(
            {
                "run_id": run.manifest.run_id,
                "artifacts": sorted(run.manifest.artifact_hashes),
                "evidence_count": len(list((run.directory / "evidence/items").glob("*.json"))),
                "divergent_artifacts": list(run.verify()),
            },
            args,
        )
        return ExitCode.OK
    path = run.directory / "evidence" / "items" / f"{reference}.json"
    if not path.is_file():
        raise ConfigError(
            "E_EVIDENCIA_AUSENTE",
            f"A evidência {reference!r} não existe na execução {run.manifest.run_id}.",
            detail={"run_id": run.manifest.run_id, "reference": reference},
        )
    _emit(json.loads(path.read_text(encoding="utf-8")), args)
    return ExitCode.OK


def _handle_replay(args: argparse.Namespace) -> ExitCode:
    """Recalcula métricas com entradas congeladas e reporta divergências."""
    resolved = _require_config(args)
    store = _store_for(resolved)
    run_id = getattr(args, "run", None)
    if run_id is None:
        team = _select_team(resolved, args)
        latest = store.latest(team.alias)
        if latest is None:
            raise ConfigError(
                "E_RUN_INEXISTENTE",
                "Não há execução persistida para reprocessar.",
                remediation="Execute 'status' antes de 'replay'.",
            )
        run_id = latest.manifest.run_id
    report, identical = replay_run(
        store, run_id, resolved=resolved, team_alias=getattr(args, "team", None)
    )
    _emit(
        {
            "run_id": run_id,
            "identical": identical,
            "report": report.model_dump(mode="json"),
        },
        args,
    )
    return ExitCode.OK if identical else ExitCode.SCHEMA_INCOMPATIBLE


def _handle_setup(args: argparse.Namespace) -> ExitCode:
    """Descobre projetos e equipes pelo MCP oficial e grava a configuração compartilhável."""
    from ado_team_compass.adapters.ado_mcp import AdoMcpClient
    from ado_team_compass.config.setup import (
        build_config_document,
        discover,
        write_config_document,
    )
    from ado_team_compass.mcp.session.official import official_transport

    if args.offline:
        raise ConfigError(
            "E_SETUP_OFFLINE",
            "O setup precisa do servidor MCP oficial para descobrir projetos e equipes.",
            remediation="Execute sem --offline após autenticar a sessão do MCP oficial.",
        )
    organization: str | None = getattr(args, "organization", None)
    if not organization:
        raise ConfigError(
            "E_SETUP_ORGANIZACAO_AUSENTE",
            "Informe a organização do Azure DevOps a ser descoberta.",
            remediation="Use --organization <nome-da-organizacao>.",
        )

    connection = _bootstrap_connection(organization)
    factory: TransportFactory = getattr(args, "_transport_factory", None) or (
        lambda conn: official_transport(conn)
    )
    with factory(connection) as transport:
        client = AdoMcpClient(transport=transport)
        discovery = discover(client, organization=organization)

    document = build_config_document(discovery)
    destination = args.output or DEFAULT_CONFIG_PATH
    write_config_document(document, destination, force=bool(getattr(args, "force", False)))
    LOGGER.info("Configuração gravada em %s", destination)
    summary = {
        "organization": organization,
        "catalog_hash": discovery.catalog_hash,
        "config_path": str(destination),
        "teams": [
            {
                "alias": alias,
                "project_id": team.project_id,
                "team_id": team.team_id,
                "team_name": team.team_name,
                "limitations": list(team.limitations),
            }
            for alias, team in discovery.aliases().items()
        ],
        "limitations": discovery.limitations,
        "next_step": "revise o perfil de cada equipe e execute 'doctor'",
    }
    sys.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return ExitCode.PARTIAL_CAPABILITY if discovery.limitations else ExitCode.OK


def _bootstrap_connection(organization: str) -> ConnectionConfig:
    """Conexão mínima para o handshake inicial: servidor remoto oficial da organização."""
    return ConnectionConfig(
        alias=organization,
        organization=organization,
        server=McpServerConfig(transport=McpTransport.HTTP),
    )


def _handle_doctor(args: argparse.Namespace) -> ExitCode:
    factory: TransportFactory | None = getattr(args, "_transport_factory", None)
    resolved = _load_optional_config(args)
    report, exit_code = diagnose(resolved, offline=args.offline, transport_factory=factory)
    _emit(report, args)
    return exit_code


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
    _Command("setup", "Resolve organização, projetos, equipes e perfis", "v0.1", _handle_setup),
    _Command(
        "doctor",
        "Diagnostica ambiente, acesso, configuração e capacidades",
        "v0.1",
        _handle_doctor,
    ),
    _Command(
        "collect",
        "Coleta apenas as fontes necessárias ao escopo e período",
        "v0.1",
        _handle_collect,
    ),
    _Command(
        "report", "Calcula e renderiza relatório de uma execução existente", "v0.1", _handle_report
    ),
    _Command("status", "Atalho para coleta atual e relatório de equipe", "v0.1", _handle_status),
    _Command(
        "allocation", "Visão de carga conhecida por pessoa/equipe", "v0.1", _handle_allocation
    ),
    _Command(
        "evidence", "Recupera evidência local por execução e referência", "v0.1", _handle_evidence
    ),
    _Command("replay", "Recalcula métricas com entradas congeladas", "v0.1", _handle_replay),
    _Command("demo", "Gera relatório com dados sintéticos, sem rede", "v0.1", _handle_demo),
    _Command("render", "Gera o HTML operacional offline", "v0.1", None),
    _Command("decisions", "Exporta e importa decisões humanas", "v0.1", None),
    _Command("history", "Métricas históricas de compromisso e fluxo", "v0.2", None),
    _Command("planning", "Achados de regras de planejamento", "v0.2", None),
    _Command("run-scheduled", "Execução agendada não interativa", "v0.3", None),
    _Command("forecast", "Projeção experimental com premissas", "v0.4", None),
)


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, help="Caminho explícito da configuração")
    parser.add_argument("--organization", help="Organização do Azure DevOps (entrada setup)")
    parser.add_argument(
        "--force", action="store_true", help="Autoriza sobrescrever a configuração existente"
    )
    parser.add_argument("--run", help="ID de uma execução persistida")
    parser.add_argument("--reference", help="Referência de evidência dentro da execução")
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
