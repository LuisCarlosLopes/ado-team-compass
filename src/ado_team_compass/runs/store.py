"""Armazenamento imutável de execuções, com escrita atômica e retenção.

Garantias:

- artefatos são gravados em arquivo temporário e renomeados: escrita interrompida não
  substitui uma execução válida por saída incompleta;
- uma execução só é marcada `complete` quando todas as fontes pedidas foram coletadas;
- execuções anteriores nunca são sobrescritas;
- hashes registram integridade, não autenticidade.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ado_team_compass import __version__
from ado_team_compass.contracts.common import SCHEMA_MAJOR, SchemaVersion
from ado_team_compass.contracts.run import RunManifest, RunState
from ado_team_compass.errors import CompassError, ConfigError, SchemaVersionError

__all__ = ["RunStore", "StoredRun", "hash_payload", "run_id_for"]

_MANIFEST = "run.json"


def hash_payload(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def run_id_for(as_of: datetime, team_alias: str) -> str:
    """ID legível e ordenável, derivado do instante de referência e da equipe."""
    stamp = as_of.astimezone(tz=None).strftime("%Y%m%dT%H%M%S")
    return f"{stamp}-{team_alias}"


@dataclass(frozen=True)
class StoredRun:
    """Execução persistida e seus artefatos."""

    directory: Path
    manifest: RunManifest

    def artifact(self, name: str) -> Any:
        path = self.directory / name
        if not path.is_file():
            raise ConfigError(
                "E_RUN_ARTEFATO_AUSENTE",
                f"O artefato {name!r} não existe na execução {self.manifest.run_id}.",
                detail={"run_id": self.manifest.run_id, "artifact": name},
            )
        return json.loads(path.read_text(encoding="utf-8"))

    def verify(self) -> tuple[str, ...]:
        """Confere os hashes registrados; devolve os artefatos divergentes."""
        divergent: list[str] = []
        for name, expected in self.manifest.artifact_hashes.items():
            path = self.directory / name
            if not path.is_file():
                divergent.append(name)
                continue
            if hash_payload(json.loads(path.read_text(encoding="utf-8"))) != expected:
                divergent.append(name)
        return tuple(divergent)


class RunStore:
    """Diretório de execuções. Nunca guarda estado no diretório instalado do plugin."""

    def __init__(self, root: Path, *, engine_version: str = __version__) -> None:
        self.root = root
        self.engine_version = engine_version

    # -- escrita -----------------------------------------------------------------
    def begin(self, run_id: str) -> Path:
        """Cria o diretório da execução; execução existente não é sobrescrita."""
        directory = self.root / run_id
        if directory.exists():
            raise ConfigError(
                "E_RUN_JA_EXISTE",
                f"A execução {run_id!r} já existe e é imutável.",
                detail={"run_id": run_id, "path": str(directory)},
                remediation="Use outro instante de referência ou consulte a execução existente.",
            )
        (directory / "evidence").mkdir(parents=True)
        return directory

    def write_json(self, directory: Path, name: str, payload: Any) -> str:
        """Grava um artefato JSON de forma atômica e devolve seu hash."""
        destination = directory / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        _atomic_write(destination, text)
        return hash_payload(json.loads(text))

    def write_text(self, directory: Path, name: str, text: str) -> None:
        destination = directory / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(destination, text)

    def finalize(
        self,
        directory: Path,
        *,
        run_id: str,
        state: RunState,
        source_identity: str,
        collection_started_at: datetime,
        collection_finished_at: datetime | None,
        as_of: datetime,
        effective_config: Mapping[str, Any],
        artifact_hashes: Mapping[str, str],
        partial_reasons: Iterable[str] = (),
        mcp_server_version: str | None = None,
        mcp_catalog_hash: str | None = None,
    ) -> StoredRun:
        """Escreve o manifesto por último: sem ele, a execução não é considerada válida."""
        reasons = tuple(partial_reasons)
        if state is RunState.COMPLETE and reasons:
            raise ConfigError(
                "E_RUN_ESTADO_INCONSISTENTE",
                "Uma execução com fontes parciais não pode ser marcada como completa.",
                detail={"run_id": run_id, "partial_reasons": list(reasons)},
            )
        manifest = RunManifest(
            run_id=run_id,
            schema_version=SchemaVersion(major=SCHEMA_MAJOR, minor=0),
            engine_version=self.engine_version,
            state=state,
            source_identity=source_identity,
            mcp_server_version=mcp_server_version,
            mcp_catalog_hash=mcp_catalog_hash,
            collection_started_at=collection_started_at,
            collection_finished_at=collection_finished_at,
            as_of=as_of,
            effective_config=dict(effective_config),
            artifact_hashes=dict(artifact_hashes),
            partial_reasons=reasons,
        )
        self.write_json(directory, _MANIFEST, manifest.model_dump(mode="json"))
        return StoredRun(directory=directory, manifest=manifest)

    def abandon(self, directory: Path, reason: str) -> None:
        """Marca uma execução interrompida sem manifesto válido, preservando o diagnóstico."""
        _atomic_write(
            directory / "INCOMPLETA.txt",
            f"Execução interrompida antes do manifesto: {reason}\n",
        )

    # -- leitura -----------------------------------------------------------------
    def load(self, run_id: str) -> StoredRun:
        directory = self.root / run_id
        path = directory / _MANIFEST
        if not path.is_file():
            raise ConfigError(
                "E_RUN_NAO_ENCONTRADA",
                f"A execução {run_id!r} não existe ou não foi finalizada.",
                detail={"run_id": run_id, "path": str(directory)},
                remediation="Liste as execuções disponíveis com 'evidence' ou colete novamente.",
            )
        payload = json.loads(path.read_text(encoding="utf-8"))
        declared = str(payload.get("schema_version", {}).get("major", "?"))
        if declared != str(SCHEMA_MAJOR):
            raise SchemaVersionError(
                "E_RUN_SCHEMA_INCOMPATIVEL",
                f"A execução {run_id!r} usa schema major {declared}, "
                f"incompatível com {SCHEMA_MAJOR}.",
                detail={"run_id": run_id, "declared": declared},
                remediation="Use a versão do motor compatível para reprocessar esta execução.",
            )
        return StoredRun(directory=directory, manifest=RunManifest.model_validate(payload))

    def list_runs(self) -> tuple[str, ...]:
        if not self.root.is_dir():
            return ()
        return tuple(
            sorted(
                entry.name
                for entry in self.root.iterdir()
                if entry.is_dir() and (entry / _MANIFEST).is_file()
            )
        )

    def latest(self, team_alias: str) -> StoredRun | None:
        for run_id in reversed(self.list_runs()):
            if run_id.endswith(f"-{team_alias}"):
                return self.load(run_id)
        return None

    # -- retenção ----------------------------------------------------------------
    def purge(self, *, now: datetime, retention_days: int) -> tuple[str, ...]:
        """Remove execuções mais antigas que a retenção configurada."""
        cutoff = now - timedelta(days=retention_days)
        removed: list[str] = []
        for run_id in self.list_runs():
            try:
                run = self.load(run_id)
            except CompassError:
                continue
            if run.manifest.as_of < cutoff:
                _remove_tree(run.directory)
                removed.append(run_id)
        return tuple(removed)


def _atomic_write(destination: Path, text: str) -> None:
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(destination)


def _remove_tree(directory: Path) -> None:
    for entry in sorted(directory.rglob("*"), reverse=True):
        if entry.is_file() or entry.is_symlink():
            entry.unlink()
        else:
            entry.rmdir()
    directory.rmdir()
