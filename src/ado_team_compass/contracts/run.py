"""Contrato de `run.json`: manifesto imutável de uma execução."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from ado_team_compass.contracts.common import SchemaVersion, StrictModel

__all__ = ["RunManifest", "RunState"]


class RunState(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class RunManifest(StrictModel):
    """Identidade, versões e hashes de uma execução; escrita de forma atômica."""

    run_id: str
    schema_version: SchemaVersion
    engine_version: str
    state: RunState
    source_identity: str = Field(description="Identidade opaca da fonte, sem dados pessoais.")
    mcp_server_version: str | None = None
    mcp_catalog_hash: str | None = None
    collection_started_at: datetime
    collection_finished_at: datetime | None = None
    as_of: datetime
    effective_config: dict[str, Any] = Field(default_factory=dict)
    artifact_hashes: dict[str, str] = Field(default_factory=dict)
    partial_reasons: tuple[str, ...] = ()
