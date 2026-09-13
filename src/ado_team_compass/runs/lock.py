"""Lock de execução e marcador de sucesso para operação agendada (T23, T24).

A chave é configuração + equipe + janela + data: duas execuções simultâneas da mesma chave
não produzem resultado duplicado, e um sucesso anterior nunca é substituído por uma falha
posterior. O lock é um arquivo criado de forma exclusiva; ele guarda apenas metadados.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ado_team_compass.errors import ConfigError

__all__ = ["ScheduleKey", "SuccessMarker", "acquire_lock", "read_marker", "write_marker"]


@dataclass(frozen=True)
class ScheduleKey:
    """Identidade de uma execução agendada."""

    config_hash: str
    team_alias: str
    window: str
    day: str

    def digest(self) -> str:
        canonical = json.dumps(
            {
                "config_hash": self.config_hash,
                "team": self.team_alias,
                "window": self.window,
                "day": self.day,
            },
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]

    @property
    def name(self) -> str:
        return f"{self.team_alias}-{self.day}-{self.digest()[:8]}"


@dataclass(frozen=True)
class SuccessMarker:
    """Registro de que a chave já produziu um resultado válido."""

    key: str
    run_id: str
    finished_at: datetime
    state: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "run_id": self.run_id,
            "finished_at": self.finished_at.isoformat(),
            "state": self.state,
        }


def _lock_path(root: Path, key: ScheduleKey) -> Path:
    return root / "locks" / f"{key.name}.lock"


def _marker_path(root: Path, key: ScheduleKey) -> Path:
    return root / "markers" / f"{key.name}.json"


@contextmanager
def acquire_lock(
    root: Path,
    key: ScheduleKey,
    *,
    now: datetime,
    owner: str = "run-scheduled",
    stale_after: timedelta = timedelta(hours=2),
) -> Iterator[Path]:
    """Garante execução única por chave; lock vivo de outro processo interrompe a execução."""
    path = _lock_path(root, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: Mapping[str, Any] = {
        "key": key.digest(),
        "owner": owner,
        "acquired_at": now.isoformat(),
        "pid": os.getpid(),
    }
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        existing = _read_json(path)
        acquired_at = _parse(existing.get("acquired_at"))
        if acquired_at is not None and now - acquired_at > stale_after:
            path.unlink(missing_ok=True)
            with acquire_lock(root, key, now=now, owner=owner, stale_after=stale_after) as held:
                yield held
            return
        raise ConfigError(
            "E_AGENDAMENTO_EM_ANDAMENTO",
            "Outra execução agendada da mesma chave está em andamento.",
            detail={"key": key.digest(), "lock": str(path)},
            remediation="Aguarde a execução corrente terminar; não há duplicação de resultado.",
        ) from error
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(dict(payload), handle, ensure_ascii=False, sort_keys=True)
        yield path
    finally:
        path.unlink(missing_ok=True)


def read_marker(root: Path, key: ScheduleKey) -> SuccessMarker | None:
    """Marcador de sucesso da chave, quando existir."""
    payload = _read_json(_marker_path(root, key))
    if not payload:
        return None
    finished_at = _parse(payload.get("finished_at"))
    if finished_at is None:
        return None
    return SuccessMarker(
        key=str(payload.get("key", "")),
        run_id=str(payload.get("run_id", "")),
        finished_at=finished_at,
        state=str(payload.get("state", "")),
    )


def write_marker(root: Path, key: ScheduleKey, marker: SuccessMarker) -> Path:
    """Grava o marcador de forma atômica após um resultado válido."""
    path = _marker_path(root, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(marker.as_dict(), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
