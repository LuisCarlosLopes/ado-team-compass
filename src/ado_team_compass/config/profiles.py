"""Carga dos perfis declarativos empacotados com o produto."""

from __future__ import annotations

from functools import cache
from importlib import resources
from typing import Any

import yaml

from ado_team_compass.contracts.config import ProfileName
from ado_team_compass.errors import ConfigError

__all__ = ["available_profiles", "load_profile"]

_PACKAGE = "ado_team_compass.profiles"


def available_profiles() -> tuple[str, ...]:
    return tuple(profile.value for profile in ProfileName)


@cache
def load_profile(name: str) -> dict[str, Any]:
    """Retorna o fragmento declarativo do perfil; perfil desconhecido é erro acionável."""
    if name not in available_profiles():
        raise ConfigError(
            "E_CFG_PERFIL_DESCONHECIDO",
            f"Perfil {name!r} não existe.",
            detail={"profile": name, "available": list(available_profiles())},
            remediation=f"Use um dos perfis: {', '.join(available_profiles())}.",
        )
    text = resources.files(_PACKAGE).joinpath(f"{name}.yaml").read_text(encoding="utf-8")
    document = yaml.safe_load(text)
    if not isinstance(document, dict):
        raise ConfigError(
            "E_CFG_PERFIL_INVALIDO",
            f"O perfil {name!r} não contém um mapeamento válido.",
            detail={"profile": name},
        )
    return document
