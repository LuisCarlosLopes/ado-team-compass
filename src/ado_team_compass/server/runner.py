"""Execução em processo das entradas da CLI, com stdout e stderr capturados.

O servidor MCP não reimplementa nenhuma regra: cada ferramenta roda a mesma entrada da CLI,
pelo mesmo handler, e devolve o mesmo JSON e o mesmo código de saída. Como stdout é o canal do
protocolo MCP, a saída do motor precisa ser capturada antes de chegar ao descritor real.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from typing import Any

from ado_team_compass.errors import ExitCode

__all__ = ["UNEXPECTED_FAILURE", "CommandResult", "run_command"]

#: Código reservado a falhas não previstas no contrato de saída do motor.
UNEXPECTED_FAILURE = 1


@dataclass(frozen=True)
class CommandResult:
    """Resultado de uma entrada da CLI executada em processo."""

    command: str
    exit_code: int
    stdout: str
    stderr: str

    @property
    def succeeded(self) -> bool:
        """Saída 0 conclui; saída 5 ainda produz relatório, mas é parcial."""
        return self.exit_code == int(ExitCode.OK)

    def payload(self) -> Any:
        """Saída do motor já desserializada; texto puro quando não for JSON."""
        text = self.stdout.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    def error(self) -> dict[str, Any] | None:
        """Erro estruturado que o motor escreve em stderr, quando houver."""
        for line in _json_candidates(self.stderr):
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and "error" in parsed:
                error = parsed["error"]
                return error if isinstance(error, dict) else {"message": str(error)}
        return None


def _json_candidates(stderr: str) -> list[str]:
    """Blocos de stderr que podem ser o JSON de erro do motor.

    O motor emite log em linhas soltas e o erro como um objeto indentado; reconstituir o
    bloco inteiro é mais simples do que analisar linha a linha.
    """
    text = stderr.strip()
    if not text:
        return []
    start = text.find("{")
    return [text[start:]] if start >= 0 else []


def run_command(argv: list[str]) -> CommandResult:
    """Roda uma entrada da CLI em processo, sem tocar nos descritores reais."""
    from ado_team_compass import cli

    out, err = io.StringIO(), io.StringIO()
    command = argv[0] if argv else ""
    try:
        with redirect_stdout(out), redirect_stderr(err):
            exit_code = int(cli.main(argv))
    except SystemExit as stop:  # argparse encerra assim em entrada inválida
        code = stop.code
        exit_code = int(code) if isinstance(code, int) else int(ExitCode.INVALID_INPUT)
    except Exception as failure:
        err.write(
            json.dumps(
                {
                    "error": {
                        "code": "E_FALHA_INESPERADA",
                        "message": f"{type(failure).__name__}: {failure}",
                        "remediation": "Repita com diagnóstico detalhado pela CLI do motor.",
                    }
                },
                ensure_ascii=False,
            )
        )
        exit_code = UNEXPECTED_FAILURE
    return CommandResult(
        command=command, exit_code=exit_code, stdout=out.getvalue(), stderr=err.getvalue()
    )
