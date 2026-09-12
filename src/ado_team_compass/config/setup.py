"""Descoberta de organização, projetos e equipes pelo MCP oficial (entrada `setup`).

A descoberta técnica não define política de gestão: o perfil é uma decisão declarada, e
qualquer atributo que o servidor não expuser gera limitação explícita com pedido de
configuração manual — nunca uma consulta direta ao Azure DevOps como alternativa.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ado_team_compass.adapters.ado_mcp import AdoMcpClient, Operation
from ado_team_compass.contracts.common import SCHEMA_MAJOR
from ado_team_compass.contracts.config import ProfileName
from ado_team_compass.errors import CapabilityUnavailable, ConfigError

__all__ = [
    "DiscoveredTeam",
    "DiscoveryResult",
    "build_config_document",
    "discover",
    "slugify",
    "write_config_document",
]

_ID_KEYS = ("id", "teamId", "projectId", "guid")
_NAME_KEYS = ("name", "displayName", "teamName", "projectName")


def slugify(value: str) -> str:
    """Alias estável e legível; nomes com acento e espaço não viram chave ambígua."""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-")
    return slug or "equipe"


@dataclass(frozen=True)
class DiscoveredTeam:
    """Equipe descoberta, sempre identificada por IDs estáveis."""

    project_id: str
    team_id: str
    project_name: str | None = None
    team_name: str | None = None
    area_paths: tuple[str, ...] = ()
    include_descendants: bool | None = None
    iterations: tuple[str, ...] = ()
    provenance: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


@dataclass
class DiscoveryResult:
    """Equipes descobertas e o que o catálogo conectado não permitiu resolver."""

    organization: str
    catalog_hash: str
    teams: list[DiscoveredTeam] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def aliases(self) -> dict[str, DiscoveredTeam]:
        """Aliases únicos; equipes homônimas são desambiguadas por projeto e ID."""
        by_name: dict[str, list[DiscoveredTeam]] = {}
        for team in self.teams:
            by_name.setdefault(slugify(team.team_name or team.team_id), []).append(team)
        aliases: dict[str, DiscoveredTeam] = {}
        for base, teams in by_name.items():
            if len(teams) == 1:
                aliases[base] = teams[0]
                continue
            for team in teams:
                project = slugify(team.project_name or team.project_id)
                candidate = f"{project}-{base}"
                if candidate in aliases:
                    candidate = f"{candidate}-{team.team_id[:8]}"
                aliases[candidate] = team
        return dict(sorted(aliases.items()))


def _entries(payload: Any) -> list[Mapping[str, Any]]:
    """Aceita lista, `{"value": [...]}` ou item único, sem presumir formato do servidor."""
    if payload is None:
        return []
    if isinstance(payload, Mapping):
        for key in ("value", "teams", "projects", "items", "iterations"):
            nested = payload.get(key)
            if isinstance(nested, list):
                return [entry for entry in nested if isinstance(entry, Mapping)]
        return [payload]
    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, Mapping)]
    return []


def _first(entry: Mapping[str, Any], keys: Sequence[str]) -> str | None:
    for key in keys:
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def discover(
    client: AdoMcpClient,
    *,
    organization: str,
    project_filter: Iterable[str] | None = None,
) -> DiscoveryResult:
    """Resolve projetos, equipes e, quando exposto, escopo de área e iterações."""
    catalog = client.catalog or client.handshake()
    result = DiscoveryResult(organization=organization, catalog_hash=catalog.catalog_hash)
    wanted = {value for value in (project_filter or ())}

    try:
        projects_payload = client.call(Operation.LIST_PROJECTS)
    except CapabilityUnavailable as error:
        result.limitations.append(
            f"projetos não descobertos pelo catálogo conectado: {error.message}"
        )
        return result

    for project in _entries(projects_payload):
        project_id = _first(project, _ID_KEYS)
        project_name = _first(project, _NAME_KEYS)
        if project_id is None:
            result.limitations.append("um projeto veio sem ID estável e foi ignorado")
            continue
        if wanted and not ({project_id, project_name or ""} & wanted):
            continue
        result.teams.extend(_discover_teams(client, result, project_id, project_name))
    if not result.teams:
        result.limitations.append("nenhuma equipe acessível foi descoberta no escopo consultado")
    return result


def _discover_teams(
    client: AdoMcpClient,
    result: DiscoveryResult,
    project_id: str,
    project_name: str | None,
) -> list[DiscoveredTeam]:
    try:
        teams_payload = client.call(Operation.LIST_TEAMS, {"project": project_id})
    except CapabilityUnavailable as error:
        result.limitations.append(
            f"equipes do projeto {project_name or project_id} não descobertas: {error.message}"
        )
        return []

    discovered: list[DiscoveredTeam] = []
    for team in _entries(teams_payload):
        team_id = _first(team, _ID_KEYS)
        if team_id is None:
            result.limitations.append(
                f"uma equipe do projeto {project_name or project_id} veio sem ID estável"
            )
            continue
        scope = _discover_scope(client, project_id, team_id)
        discovered.append(
            DiscoveredTeam(
                project_id=project_id,
                team_id=team_id,
                project_name=project_name,
                team_name=_first(team, _NAME_KEYS),
                area_paths=scope["area_paths"],
                include_descendants=scope["include_descendants"],
                iterations=scope["iterations"],
                provenance=scope["provenance"],
                limitations=scope["limitations"],
            )
        )
    return discovered


def _discover_scope(client: AdoMcpClient, project_id: str, team_id: str) -> dict[str, Any]:
    area_paths: tuple[str, ...] = ()
    include_descendants: bool | None = None
    iterations: tuple[str, ...] = ()
    provenance: list[str] = []
    limitations: list[str] = []

    try:
        settings = client.call(
            Operation.GET_TEAM_SETTINGS, {"project": project_id, "team": team_id}
        )
    except CapabilityUnavailable:
        settings = None
        limitations.append(
            "configuração da equipe não exposta pelo catálogo conectado: informe "
            "scope.area_paths e scope.include_descendants explicitamente"
        )
    if isinstance(settings, Mapping):
        area_paths, include_descendants, missing = _team_field_values(settings)
        if area_paths:
            provenance.append("mcp:get_team_settings")
        if missing:
            limitations.append(missing)

    try:
        iterations_payload = client.call(
            Operation.LIST_ITERATIONS, {"project": project_id, "team": team_id}
        )
    except CapabilityUnavailable:
        limitations.append(
            "iterações não expostas pelo catálogo conectado: métricas de sprint ficam "
            "indisponíveis até configuração explícita"
        )
    else:
        names = [
            name
            for entry in _entries(iterations_payload)
            if (name := _first(entry, ("path", "name", "iterationPath"))) is not None
        ]
        iterations = tuple(names)
        if names:
            provenance.append("mcp:list_iterations")

    return {
        "area_paths": area_paths,
        "include_descendants": include_descendants,
        "iterations": iterations,
        "provenance": tuple(provenance),
        "limitations": tuple(limitations),
    }


def _team_field_values(
    settings: Mapping[str, Any],
) -> tuple[tuple[str, ...], bool | None, str | None]:
    """Lê áreas da equipe apenas do que o MCP devolveu; ausência é limitação declarada."""
    raw = settings.get("teamFieldValues") or settings.get("areas") or settings.get("values")
    entries = _entries(raw) if raw is not None else []
    paths: list[str] = []
    include_children: list[bool] = []
    for entry in entries:
        value = _first(entry, ("value", "path", "areaPath", "name"))
        if value is None:
            continue
        paths.append(value)
        child_flag = entry.get("includeChildren")
        if isinstance(child_flag, bool):
            include_children.append(child_flag)
    if not paths:
        return (
            (),
            None,
            (
                "áreas da equipe não vieram na resposta do MCP: configure scope.area_paths "
                "com proveniência ou a análise por área fica indisponível"
            ),
        )
    include_descendants = all(include_children) if include_children else None
    missing = None
    if include_descendants is None:
        missing = (
            "a resposta não informou inclusão de áreas descendentes: configure "
            "scope.include_descendants explicitamente"
        )
    return tuple(paths), include_descendants, missing


def build_config_document(
    discovery: DiscoveryResult,
    *,
    connection_alias: str | None = None,
    profiles: Mapping[str, ProfileName | str] | None = None,
    timezone: str = "UTC",
) -> dict[str, Any]:
    """Monta o documento de configuração compartilhável, sem nenhum segredo."""
    alias = connection_alias or slugify(discovery.organization)
    chosen = {key: str(value) for key, value in (profiles or {}).items()}
    teams: list[dict[str, Any]] = []
    for team_alias, team in discovery.aliases().items():
        profile = chosen.get(team_alias, ProfileName.SPRINT_WITHOUT_HOURS.value)
        entry: dict[str, Any] = {
            "alias": team_alias,
            "connection": alias,
            "project_id": team.project_id,
            "team_id": team.team_id,
            "profile": profile,
            "calendar": {"timezone": timezone},
        }
        if team.project_name:
            entry["project_name"] = team.project_name
        if team.team_name:
            entry["team_name"] = team.team_name
        scope: dict[str, Any] = {}
        if team.area_paths:
            scope["area_paths"] = list(team.area_paths)
        if team.include_descendants is not None:
            scope["include_descendants"] = team.include_descendants
        if scope:
            entry["scope"] = scope
        teams.append(entry)

    return {
        "schema_version": f"{SCHEMA_MAJOR}.0",
        "connections": [
            {
                "alias": alias,
                "organization": discovery.organization,
                "server": {"name": "azure-devops", "transport": "http"},
            }
        ],
        "teams": teams,
    }


def write_config_document(document: Mapping[str, Any], path: Path, *, force: bool = False) -> Path:
    """Grava a configuração compartilhável; execução anterior nunca é sobrescrita sem pedido."""
    if path.exists() and not force:
        raise ConfigError(
            "E_CFG_JA_EXISTE",
            f"A configuração {path} já existe e não foi sobrescrita.",
            detail={"path": str(path)},
            remediation="Revise o arquivo atual ou grave em outro caminho com --output.",
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(dict(document), allow_unicode=True, sort_keys=False)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)
    return path
