"""Aviso de sessão opcional: informa a idade da última execução local.

Este hook lê apenas metadados já gravados na máquina. Ele não coleta, não autentica, não
acessa o Azure DevOps e não executa nenhuma entrada da CLI.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

RUNS = Path(os.environ.get("ADO_TEAM_COMPASS_RUNS", ".ado-team-compass/runs"))
STALE_HOURS = 24


def main() -> int:
    if not RUNS.is_dir():
        return 0
    manifests = sorted(RUNS.glob("*/run.json"))
    if not manifests:
        return 0
    latest = manifests[-1]
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
        as_of = datetime.fromisoformat(str(payload["as_of"]))
    except (json.JSONDecodeError, KeyError, ValueError):
        return 0
    age_hours = (datetime.now(UTC) - as_of).total_seconds() / 3600
    state = payload.get("state", "desconhecido")
    if age_hours > STALE_HOURS:
        sys.stdout.write(
            f"ADO Team Compass: a execução local mais recente tem {age_hours:.0f} horas "
            f"(estado {state}). Rode 'ado-team-compass status' para atualizar.\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
