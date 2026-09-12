"""Leitura, precedência e sanitização da configuração (plano 4.1.2, arquitetura D03).

Precedência determinística, do mais fraco para o mais forte:

1. `product_default` — valores padrão dos modelos tipados;
2. `profile` — fragmento declarativo do perfil nomeado;
3. `team` — entrada da equipe em `config.yaml`;
4. `local` — `config.local.yaml`, dados pessoais e ajustes da máquina;
5. `run` — opções da execução.

Segredos não são representáveis: qualquer chave com aparência de credencial é recusada.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ado_team_compass.config.merge import PRODUCT_DEFAULT, merge_layers
from ado_team_compass.config.profiles import load_profile
from ado_team_compass.contracts.common import SCHEMA_MAJOR, SchemaVersion, StrictModel
from ado_team_compass.contracts.config import CompassConfig
from ado_team_compass.errors import ConfigError, SchemaVersionError, sanitize_detail

__all__ = ["LAYER_ORDER", "ResolvedConfig", "load_config", "load_yaml_document", "resolve_config"]

LAYER_ORDER = (PRODUCT_DEFAULT, "profile", "team", "local", "run")

_FORBIDDEN_KEYS = (
    "pat",
    "token",
    "secret",
    "password",
    "senha",
    "credential",
    "client_secret",
    "authorization",
)


class ResolvedConfig(StrictModel):
    """Configuração validada, proveniência por chave e cópia efetiva sanitizada."""

    config: CompassConfig
    provenance: dict[str, str]
    effective: dict[str, Any]

    def layer_of(self, path: str) -> str:
        return self.provenance.get(path, PRODUCT_DEFAULT)


def _reject_secrets(document: Mapping[str, Any], prefix: str = "") -> None:
    for key, value in document.items():
        path = f"{prefix}{key}"
        if any(
            forbidden == key.lower() or key.lower().endswith(f"_{forbidden}")
            for forbidden in _FORBIDDEN_KEYS
        ):
            raise ConfigError(
                "E_CFG_SEGREDO_NA_CONFIGURACAO",
                f"A chave {path!r} parece conter credencial e não é aceita na configuração.",
                detail={"path": path},
                remediation=(
                    "Remova a credencial e configure a sessão no cliente MCP oficial; "
                    "a configuração guarda apenas a referência 'session_ref'."
                ),
            )
        if isinstance(value, Mapping):
            _reject_secrets(value, f"{path}.")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, Mapping):
                    _reject_secrets(item, f"{path}[{index}].")


def load_yaml_document(path: Path) -> dict[str, Any]:
    """Carrega YAML com `safe_load`; nenhuma tag customizada ou código é avaliado."""
    if not path.is_file():
        raise ConfigError(
            "E_CFG_ARQUIVO_AUSENTE",
            f"Arquivo de configuração não encontrado: {path}.",
            detail={"path": str(path)},
            remediation="Informe --config ou execute 'setup' para gerar a configuração.",
        )
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ConfigError(
            "E_CFG_YAML_INVALIDO",
            f"Não foi possível interpretar o YAML de {path}.",
            detail={"path": str(path), "reason": str(error)},
            remediation="Corrija a sintaxe indicada e execute novamente.",
        ) from error
    if document is None:
        document = {}
    if not isinstance(document, dict):
        raise ConfigError(
            "E_CFG_ESTRUTURA_INVALIDA",
            f"A configuração em {path} deve ser um mapeamento.",
            detail={"path": str(path)},
        )
    _reject_secrets(document)
    return document


def _check_schema_version(document: Mapping[str, Any]) -> SchemaVersion:
    raw = document.get("schema_version")
    if raw is None:
        raise ConfigError(
            "E_CFG_SCHEMA_AUSENTE",
            "A configuração precisa declarar 'schema_version'.",
            remediation=f"Adicione schema_version: '{SCHEMA_MAJOR}.0'.",
        )
    try:
        version = SchemaVersion.parse(str(raw))
    except ValueError as error:
        raise ConfigError(
            "E_CFG_SCHEMA_INVALIDO",
            str(error),
            detail={"schema_version": str(raw)},
        ) from error
    if version.major != SCHEMA_MAJOR:
        raise SchemaVersionError(
            "E_CFG_SCHEMA_MAJOR_DESCONHECIDA",
            f"A configuração declara schema major {version.major}, "
            f"incompatível com {SCHEMA_MAJOR} desta instalação.",
            detail={"declared": str(version), "supported_major": SCHEMA_MAJOR},
            remediation="Migre a configuração ou instale a versão compatível do motor.",
        )
    return version


def _team_layers(
    team_document: Mapping[str, Any],
    local_teams: Mapping[str, Any],
    run_overrides: Mapping[str, Any],
) -> list[tuple[str, Mapping[str, Any]]]:
    alias = str(team_document.get("alias", ""))
    profile = str(team_document.get("profile", "sprint_with_capacity"))
    layers: list[tuple[str, Mapping[str, Any]]] = [("profile", load_profile(profile))]
    layers.append(("team", team_document))
    local_fragment = local_teams.get(alias)
    if isinstance(local_fragment, Mapping):
        layers.append(("local", local_fragment))
    for key in ("*", alias):
        fragment = run_overrides.get(key)
        if isinstance(fragment, Mapping):
            layers.append(("run", fragment))
    return layers


def resolve_config(
    document: Mapping[str, Any],
    *,
    local_document: Mapping[str, Any] | None = None,
    run_overrides: Mapping[str, Any] | None = None,
) -> ResolvedConfig:
    """Aplica a precedência, valida os modelos e devolve a configuração efetiva sanitizada."""
    _reject_secrets(document)
    version = _check_schema_version(document)
    local = dict(local_document or {})
    overrides = dict(run_overrides or {})
    _reject_secrets(local)
    _reject_secrets(overrides)

    local_teams = local.get("teams") or {}
    if not isinstance(local_teams, Mapping):
        raise ConfigError(
            "E_CFG_LOCAL_INVALIDO",
            "Em config.local.yaml, 'teams' deve ser um mapeamento por alias de equipe.",
            detail={"received": type(local_teams).__name__},
        )
    run_teams = overrides.get("teams") or {}
    if not isinstance(run_teams, Mapping):
        raise ConfigError(
            "E_CFG_OVERRIDE_INVALIDO",
            "Os overrides de execução devem usar 'teams' como mapeamento por alias.",
            detail={"received": type(run_teams).__name__},
        )

    raw_teams = document.get("teams")
    if not isinstance(raw_teams, list) or not raw_teams:
        raise ConfigError(
            "E_CFG_EQUIPES_AUSENTES",
            "A configuração precisa declarar a lista 'teams' com ao menos uma equipe.",
            remediation="Execute 'setup' para descobrir projetos e equipes pelo MCP oficial.",
        )

    provenance: dict[str, str] = {}
    resolved_teams: list[dict[str, Any]] = []
    for index, raw_team in enumerate(raw_teams):
        if not isinstance(raw_team, Mapping):
            raise ConfigError(
                "E_CFG_EQUIPE_INVALIDA",
                f"A equipe na posição {index} deve ser um mapeamento.",
                detail={"index": index},
            )
        merged, team_provenance = merge_layers(_team_layers(raw_team, local_teams, run_teams))
        alias = str(merged.get("alias", index))
        for path, layer in team_provenance.items():
            provenance[f"teams.{alias}.{path}"] = layer
        resolved_teams.append(merged)

    top_layers: list[tuple[str, Mapping[str, Any]]] = [
        ("team", {"output": document.get("output") or {}}),
    ]
    if isinstance(local.get("output"), Mapping):
        top_layers.append(("local", {"output": local["output"]}))
    if isinstance(overrides.get("output"), Mapping):
        top_layers.append(("run", {"output": overrides["output"]}))
    merged_top, top_provenance = merge_layers(top_layers)
    provenance.update(top_provenance)

    payload = {
        "schema_version": {"major": version.major, "minor": version.minor},
        "connections": document.get("connections") or [],
        "teams": resolved_teams,
        "output": merged_top.get("output") or {},
    }
    try:
        config = CompassConfig.model_validate(payload)
    except ValidationError as error:
        raise ConfigError(
            "E_CFG_INVALIDA",
            "A configuração resolvida é inválida.",
            detail={"violations": _violations(error)},
            remediation="Corrija os campos indicados; nenhum valor é assumido implicitamente.",
        ) from error

    effective = sanitize_detail(config.model_dump(mode="json"))
    return ResolvedConfig(config=config, provenance=provenance, effective=effective)


def _violations(error: ValidationError) -> list[dict[str, Any]]:
    return [
        {"path": ".".join(str(part) for part in item["loc"]), "message": item["msg"]}
        for item in error.errors()
    ]


def load_config(
    path: Path,
    *,
    local_path: Path | None = None,
    run_overrides: Mapping[str, Any] | None = None,
) -> ResolvedConfig:
    """Carrega `config.yaml` e, quando existir, `config.local.yaml` ao lado dele."""
    document = load_yaml_document(path)
    resolved_local: dict[str, Any] | None = None
    candidate = local_path or path.with_name("config.local.yaml")
    if candidate.is_file():
        resolved_local = load_yaml_document(candidate)
    return resolve_config(document, local_document=resolved_local, run_overrides=run_overrides)
