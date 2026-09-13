"""Modelo tipado da configuração compartilhável (plano 4.1.2).

Nenhum campo aceita código executável e nenhuma credencial de acesso ao Azure DevOps é
representável: a conexão referencia apenas a sessão segura do cliente MCP oficial.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Self
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, model_validator

from ado_team_compass.contracts.common import Capability, SchemaVersion, StrictModel

__all__ = [
    "DIRECT_ADO_HOSTS",
    "OFFICIAL_REMOTE_URL_TEMPLATE",
    "AllocationConfig",
    "BugBehavior",
    "CalendarConfig",
    "CompassConfig",
    "ConnectionConfig",
    "CurrentDayPolicy",
    "HistoryConfig",
    "McpTransport",
    "OutputConfig",
    "PlanningConfig",
    "PlanningRule",
    "ProcessConfig",
    "ProfileName",
    "ScopeConfig",
    "StateCategory",
    "TeamConfig",
    "Thresholds",
]


class McpTransport(StrEnum):
    STDIO = "stdio"
    HTTP = "http"


class ProfileName(StrEnum):
    SPRINT_WITH_CAPACITY = "sprint_with_capacity"
    SPRINT_WITHOUT_HOURS = "sprint_without_hours"
    CONTINUOUS_FLOW = "continuous_flow"


class StateCategory(StrEnum):
    """Categoria de estado mapeada localmente; nunca inferida por string global."""

    PROPOSED = "proposed"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    COMPLETED = "completed"
    REMOVED = "removed"


class BugBehavior(StrEnum):
    AS_REQUIREMENT = "as_requirement"
    AS_TASK = "as_task"
    EXCLUDED = "excluded"


class CurrentDayPolicy(StrEnum):
    EXCLUDE = "exclude"
    INCLUDE_FULL = "include_full"


#: Servidor remoto oficial recomendado pela Microsoft; a organização compõe o caminho.
OFFICIAL_REMOTE_URL_TEMPLATE = "https://mcp.azuredevops.com/{organization}/mcp"

#: Hosts que são API direta do Azure DevOps e, por isso, nunca são endpoint de MCP.
DIRECT_ADO_HOSTS = (
    "dev.azure.com",
    "analytics.dev.azure.com",
    "vsaex.dev.azure.com",
    "vssps.dev.azure.com",
    "visualstudio.com",
)


class McpServerConfig(StrictModel):
    """Servidor MCP oficial. `session_ref` nomeia uma sessão do cliente, não um segredo.

    O transporte padrão é o servidor remoto oficial; `stdio` atende cenários que exigem o
    pacote oficial local. `url` ausente em transporte http usa o endpoint remoto oficial.
    """

    name: str = "azure-devops"
    transport: McpTransport = McpTransport.HTTP
    command: tuple[str, ...] = ()
    url: str | None = None
    expected_version: str | None = None
    expected_catalog_hash: str | None = None
    session_ref: str | None = None
    env_ref: str | None = Field(
        default=None,
        description=(
            "Referência 'caminho#servidor' a uma configuração de MCP do host, de onde o "
            "ambiente do processo (incluindo a credencial da sessão) é lido na conexão. "
            "Apenas a referência é guardada: nenhum segredo entra nesta configuração."
        ),
    )

    @model_validator(mode="after")
    def _validate_transport(self) -> Self:
        if self.env_ref is not None and "#" not in self.env_ref:
            msg = "env_ref usa o formato 'caminho/para/mcp.json#nome-do-servidor'."
            raise ValueError(msg)
        if self.transport is McpTransport.STDIO and not self.command:
            msg = "Transporte stdio exige o comando do servidor MCP oficial."
            raise ValueError(msg)
        if self.url is not None:
            _validate_mcp_url(self.url)
        return self

    def resolved_url(self, organization: str) -> str:
        """URL efetiva do servidor remoto oficial para a organização configurada."""
        if self.url is not None:
            return self.url
        return OFFICIAL_REMOTE_URL_TEMPLATE.format(organization=organization)


def _validate_mcp_url(url: str) -> None:
    """Recusa endpoint que não seja HTTPS e qualquer API direta do Azure DevOps."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        msg = f"O servidor MCP exige HTTPS: {url!r}."
        raise ValueError(msg)
    host = (parsed.hostname or "").lower()
    if any(host == direct or host.endswith(f".{direct}") for direct in DIRECT_ADO_HOSTS):
        msg = (
            f"O host {host!r} é API direta do Azure DevOps e não é um servidor MCP. "
            "Use o servidor MCP oficial."
        )
        raise ValueError(msg)
    if "_apis" in parsed.path or "odata" in parsed.path.lower():
        msg = f"O caminho {parsed.path!r} é de API direta do Azure DevOps, não de MCP."
        raise ValueError(msg)


class ConnectionConfig(StrictModel):
    alias: str
    organization: str
    server: McpServerConfig


class ScopeConfig(StrictModel):
    area_paths: tuple[str, ...] = ()
    include_descendants: bool = True
    iterations: tuple[str, ...] = ()
    item_types: tuple[str, ...] = ()
    bug_behavior: BugBehavior = BugBehavior.AS_REQUIREMENT


class ProcessConfig(StrictModel):
    remaining_work_field: str | None = None
    original_estimate_field: str | None = None
    completed_work_field: str | None = None
    story_points_field: str | None = None
    accounting_level: str | None = Field(
        default=None,
        description="Nível único de contabilização de carga, por exemplo 'leaf_task'.",
    )
    state_categories: dict[str, StateCategory] = Field(default_factory=dict)
    blocked_states: tuple[str, ...] = ()
    impediment_source: str | None = None
    sprint_goal_source: str | None = None
    wip_limits: dict[str, int] = Field(default_factory=dict)


class Thresholds(StrictModel):
    """Fronteiras das classes de carga (plano 4.1.4)."""

    below_range: Decimal = Decimal("0.60")
    within_range: Decimal = Decimal("0.90")
    attention: Decimal = Decimal("1.10")

    @model_validator(mode="after")
    def _validate_order(self) -> Self:
        if not self.below_range < self.within_range < self.attention:
            msg = "Os limiares devem crescer: below_range < within_range < attention."
            raise ValueError(msg)
        return self


class PersonalAvailability(StrictModel):
    """Disponibilidade global informada explicitamente; nunca inferida."""

    person: str
    unit: str
    per_day: Decimal = Field(gt=0)
    source: str


class CalendarConfig(StrictModel):
    timezone: str = "UTC"
    working_days: tuple[int, ...] = (0, 1, 2, 3, 4)
    holidays: tuple[date, ...] = ()
    team_days_off: tuple[date, ...] = ()
    current_day_policy: CurrentDayPolicy = CurrentDayPolicy.EXCLUDE

    @model_validator(mode="after")
    def _validate_timezone_and_days(self) -> Self:
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            msg = f"Timezone IANA desconhecido: {self.timezone!r}."
            raise ValueError(msg) from error
        if any(day < 0 or day > 6 for day in self.working_days):
            msg = "Dias trabalhados usam 0=segunda a 6=domingo."
            raise ValueError(msg)
        return self


class AllocationConfig(StrictModel):
    unit: str = "hours"
    thresholds: Thresholds = Thresholds()
    personal_availability: tuple[PersonalAvailability, ...] = ()
    hours_per_day_factor: Decimal | None = Field(
        default=None,
        gt=0,
        description="Fator explícito para converter dias em horas; ausente proíbe conversão.",
    )


class HistoryConfig(StrictModel):
    commitment_at: str | None = None
    cohort: str = "first_completion"
    window_days: int = Field(default=84, ge=1)
    reopen_policy: str = "separate_metric"


class PlanningRule(StrictModel):
    enabled: bool = False
    severity: str = "info"
    tolerance_days: int = Field(default=0, ge=0)
    exceptions: tuple[str, ...] = ()


class PlanningConfig(StrictModel):
    rules: dict[str, PlanningRule] = Field(default_factory=dict)


class OutputConfig(StrictModel):
    directory: str = ".ado-team-compass/runs"
    language: str = "pt-BR"
    summary_limit_bytes: int = Field(default=24576, ge=1024)
    retention_days: int = Field(default=30, ge=1)
    fields: tuple[str, ...] = ()


class TeamConfig(StrictModel):
    """Equipe identificada por IDs estáveis; nomes servem apenas para exibição."""

    alias: str
    connection: str
    project_id: str
    team_id: str
    project_name: str | None = None
    team_name: str | None = None
    display_name: str | None = None
    profile: ProfileName = ProfileName.SPRINT_WITH_CAPACITY
    capabilities: tuple[Capability, ...] = (Capability.CURRENT_STATUS,)
    scope: ScopeConfig = ScopeConfig()
    process: ProcessConfig = ProcessConfig()
    calendar: CalendarConfig = CalendarConfig()
    allocation: AllocationConfig = AllocationConfig()
    history: HistoryConfig = HistoryConfig()
    planning: PlanningConfig = PlanningConfig()


class CompassConfig(StrictModel):
    """Configuração completa já resolvida por precedência."""

    schema_version: SchemaVersion
    connections: tuple[ConnectionConfig, ...]
    teams: tuple[TeamConfig, ...]
    output: OutputConfig = OutputConfig()

    @model_validator(mode="after")
    def _validate_references(self) -> Self:
        if not self.teams:
            msg = "Configuração exige ao menos uma equipe."
            raise ValueError(msg)
        aliases = [connection.alias for connection in self.connections]
        if len(set(aliases)) != len(aliases):
            msg = "Aliases de conexão devem ser únicos."
            raise ValueError(msg)
        team_keys = [(team.project_id, team.team_id) for team in self.teams]
        if len(set(team_keys)) != len(team_keys):
            msg = "Cada equipe deve aparecer uma vez por projeto e ID."
            raise ValueError(msg)
        team_aliases = [team.alias for team in self.teams]
        if len(set(team_aliases)) != len(team_aliases):
            msg = "Aliases de equipe devem ser únicos para permitir seleção inequívoca."
            raise ValueError(msg)
        for team in self.teams:
            if team.connection not in aliases:
                msg = (
                    f"A equipe {team.alias!r} referencia a conexão {team.connection!r}, "
                    "que não está declarada."
                )
                raise ValueError(msg)
        return self

    def team(self, selector: str) -> TeamConfig:
        """Resolve equipe por alias ou ID; ambiguidade é erro do chamador."""
        for team in self.teams:
            if selector in (team.alias, team.team_id):
                return team
        msg = f"Equipe {selector!r} não encontrada na configuração."
        raise KeyError(msg)
