"""Entrada do servidor MCP sobre stdio.

stdout é o canal do protocolo: nada além das mensagens MCP pode ser escrito nele. O log vai
para stderr antes de qualquer execução do motor, para que a CLI não prenda o logging a um
buffer capturado.
"""

from __future__ import annotations

import logging
import sys

__all__ = ["main"]


async def _serve() -> None:
    from mcp.server.stdio import stdio_server

    from ado_team_compass.server.app import build_server

    server = build_server()
    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options)


def main(argv: list[str] | None = None) -> int:
    """Sobe o servidor MCP até o host encerrar a conexão."""
    import anyio

    arguments = sys.argv[1:] if argv is None else argv
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.DEBUG if {"-v", "--verbose"} & set(arguments) else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        anyio.run(_serve)
    except KeyboardInterrupt:  # pragma: no cover - encerramento pelo host
        return 0
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
