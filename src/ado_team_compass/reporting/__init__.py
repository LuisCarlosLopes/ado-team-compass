"""Renderização determinística: resumo limitado, Markdown e HTML."""

from ado_team_compass.reporting.markdown import render_markdown
from ado_team_compass.reporting.summary import build_summary

__all__ = ["build_summary", "render_markdown"]
