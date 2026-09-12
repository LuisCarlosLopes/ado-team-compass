"""Exportação dos schemas JSON dos contratos versionados."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ado_team_compass.contracts.common import SCHEMA_MAJOR
from ado_team_compass.contracts.config import CompassConfig
from ado_team_compass.contracts.decisions import DecisionLog
from ado_team_compass.contracts.facts import FactSet
from ado_team_compass.contracts.metrics import MetricSet, Summary
from ado_team_compass.contracts.narrative import Narrative
from ado_team_compass.contracts.run import RunManifest

__all__ = ["CONTRACTS", "export_schemas", "schema_of"]

CONTRACTS: dict[str, type[BaseModel]] = {
    "config": CompassConfig,
    "facts": FactSet,
    "metrics": MetricSet,
    "summary": Summary,
    "run": RunManifest,
    "narrative": Narrative,
    "decisions": DecisionLog,
}


def schema_of(name: str) -> dict[str, Any]:
    """Schema JSON de um contrato, com a major do schema anotada."""
    model = CONTRACTS[name]
    schema: dict[str, Any] = dict(model.model_json_schema())
    schema["x-schema-major"] = SCHEMA_MAJOR
    schema["$id"] = f"https://ado-team-compass.invalid/schemas/{SCHEMA_MAJOR}/{name}.json"
    return schema


def export_schemas(directory: Path) -> list[Path]:
    """Grava um arquivo por contrato e devolve os caminhos escritos, em ordem estável."""
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in sorted(CONTRACTS):
        destination = directory / f"{name}.schema.json"
        payload = json.dumps(schema_of(name), ensure_ascii=False, indent=2, sort_keys=True)
        destination.write_text(payload + "\n", encoding="utf-8")
        written.append(destination)
    return written
