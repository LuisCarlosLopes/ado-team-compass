"""Registro humano de decisões: exportação, importação explícita e deduplicação.

O registro é local e explícito. Nada é sincronizado automaticamente e nada é escrito no
Azure DevOps. IDs permanecem estáveis por regra e entidade: um achado que reaparece em outra
execução não vira automaticamente uma nova decisão.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ado_team_compass.contracts.decisions import Decision, DecisionLog
from ado_team_compass.errors import ConfigError

__all__ = ["export_decisions", "import_decisions", "merge_decisions"]


def export_decisions(log: DecisionLog, path: Path) -> Path:
    """Grava o registro de decisões de forma atômica."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        log.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True, default=str
    )
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(payload + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def import_decisions(payload: Mapping[str, Any] | Path) -> DecisionLog:
    """Importa um registro explicitamente; arquivo inválido é erro acionável."""
    if isinstance(payload, Path):
        if not payload.is_file():
            raise ConfigError(
                "E_DECISOES_ARQUIVO_AUSENTE",
                f"O arquivo de decisões {payload} não existe.",
                detail={"path": str(payload)},
            )
        try:
            data = json.loads(payload.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ConfigError(
                "E_DECISOES_JSON_INVALIDO",
                f"O arquivo de decisões {payload} não é JSON válido.",
                detail={"path": str(payload), "reason": str(error)},
            ) from error
    else:
        data = dict(payload)
    try:
        return DecisionLog.model_validate(data)
    except ValidationError as error:
        raise ConfigError(
            "E_DECISOES_INVALIDAS",
            "O registro de decisões não segue o contrato.",
            detail={
                "violations": [
                    {"path": ".".join(str(part) for part in item["loc"]), "message": item["msg"]}
                    for item in error.errors()
                ]
            },
            remediation="Corrija os campos indicados; snapshots antigos não são editados.",
        ) from error


def merge_decisions(*logs: Iterable[Decision] | DecisionLog) -> DecisionLog:
    """Une registros preservando a primeira ocorrência de cada ID estável."""
    decisions: list[Decision] = []
    for log in logs:
        entries = log.decisions if isinstance(log, DecisionLog) else tuple(log)
        decisions.extend(entries)
    return DecisionLog(decisions=DecisionLog(decisions=tuple(decisions)).deduplicated())
