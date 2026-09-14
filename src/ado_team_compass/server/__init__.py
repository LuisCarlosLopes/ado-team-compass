"""Servidor MCP do motor: o host de IA fala com o Compass por ferramentas, não por shell."""

from ado_team_compass.server.app import INSTRUCTIONS, build_server, describe, envelope
from ado_team_compass.server.catalog import TOOLS, ToolSpec, tool_by_name
from ado_team_compass.server.runner import CommandResult, run_command

__all__ = [
    "INSTRUCTIONS",
    "TOOLS",
    "CommandResult",
    "ToolSpec",
    "build_server",
    "describe",
    "envelope",
    "run_command",
    "tool_by_name",
]
