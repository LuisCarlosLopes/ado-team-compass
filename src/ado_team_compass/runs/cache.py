"""Cache de coleta isolado por organização, identidade, escopo, período e versão.

Trocar de identidade nunca reutiliza o cache de outra pessoa: a identidade entra na chave
como hash opaco. O cache guarda respostas normalizadas, nunca credenciais.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ado_team_compass.contracts.common import SCHEMA_MAJOR

__all__ = ["CacheKey", "CollectionCache"]


@dataclass(frozen=True)
class CacheKey:
    """Chave de cache. Qualquer diferença de escopo produz entrada distinta."""

    organization: str
    identity: str
    team_id: str
    scope: str
    period: str
    engine_version: str
    schema_major: int = SCHEMA_MAJOR

    def digest(self) -> str:
        canonical = json.dumps(
            {
                "organization": self.organization,
                "identity": hashlib.sha256(self.identity.encode("utf-8")).hexdigest(),
                "team_id": self.team_id,
                "scope": self.scope,
                "period": self.period,
                "engine_version": self.engine_version,
                "schema_major": self.schema_major,
            },
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


class CollectionCache:
    """Cache local em disco, com validade explícita e isolamento por chave."""

    def __init__(self, root: Path, *, ttl: timedelta = timedelta(minutes=15)) -> None:
        self.root = root
        self.ttl = ttl

    def _path(self, key: CacheKey) -> Path:
        return self.root / key.organization / f"{key.digest()}.json"

    def get(self, key: CacheKey, *, now: datetime) -> Any | None:
        path = self._path(key)
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        stored_at = datetime.fromisoformat(str(payload.get("stored_at")))
        if now - stored_at > self.ttl:
            return None
        return payload.get("data")

    def put(self, key: CacheKey, data: Any, *, now: datetime) -> Path:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: Mapping[str, Any] = {"stored_at": now.isoformat(), "data": data}
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
            encoding="utf-8",
        )
        temporary.replace(path)
        return path

    def clear(self) -> None:
        if not self.root.is_dir():
            return
        for path in sorted(self.root.rglob("*.json")):
            path.unlink()
