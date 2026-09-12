"""Mesclagem determinística de camadas de configuração com proveniência por chave."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

__all__ = ["PRODUCT_DEFAULT", "merge_layers"]

PRODUCT_DEFAULT = "product_default"


def _merge_into(
    target: dict[str, Any],
    source: Mapping[str, Any],
    layer: str,
    provenance: dict[str, str],
    prefix: str,
) -> None:
    for key, value in source.items():
        path = f"{prefix}{key}"
        if isinstance(value, Mapping):
            nested = target.get(key)
            if not isinstance(nested, dict):
                nested = {}
                target[key] = nested
            _merge_into(nested, value, layer, provenance, f"{path}.")
        else:
            # Listas substituem integralmente: não existe mescla implícita de coleções.
            target[key] = (
                list(value)
                if isinstance(value, Sequence) and not isinstance(value, str | bytes)
                else value
            )
            provenance[path] = layer


def merge_layers(
    layers: Sequence[tuple[str, Mapping[str, Any]]],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Aplica as camadas na ordem dada; a última vence e registra a origem de cada folha."""
    merged: dict[str, Any] = {}
    provenance: dict[str, str] = {}
    for layer, document in layers:
        _merge_into(merged, document, layer, provenance, "")
    return merged, provenance
