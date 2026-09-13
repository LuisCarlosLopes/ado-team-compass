"""Ponto de entrada para execução com python -m ado_team_compass."""

from __future__ import annotations

import sys

from ado_team_compass.cli import main

__all__ = ["main"]

if __name__ == "__main__":
    # Encaminha os argumentos de linha de comando para o ponto de entrada principal
    sys.exit(main())
