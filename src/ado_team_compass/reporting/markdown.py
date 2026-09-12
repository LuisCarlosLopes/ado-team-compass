"""Renderização determinística do relatório em Markdown.

O template não recebe texto livre da fonte além dos achados produzidos pelo motor, e todo
valor é formatado a partir das métricas — nada é recalculado aqui.
"""

from __future__ import annotations

from decimal import Decimal

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from ado_team_compass.contracts.common import Coverage, Quantity
from ado_team_compass.contracts.metrics import Metric
from ado_team_compass.contracts.narrative import Narrative
from ado_team_compass.contracts.report import TeamReport

__all__ = ["render_markdown", "render_narrative_section"]


def _fmt_quantity(quantity: Quantity | None) -> str:
    if quantity is None:
        return "não aplicável"
    if quantity.value is None:
        return "ausente"
    return f"{_fmt_decimal(quantity.value)} {quantity.unit}"


def _fmt_decimal(value: Decimal) -> str:
    quantized = value.quantize(Decimal("0.01")) if value % 1 else value.quantize(Decimal("1"))
    return f"{quantized}".rstrip("0").rstrip(".") if "." in str(quantized) else str(quantized)


def _fmt_ratio(ratio: Decimal | None) -> str:
    if ratio is None:
        return "nulo"
    return f"{(ratio * 100).quantize(Decimal('0.1'))}%"


def _fmt_coverage(coverage: Coverage) -> str:
    if coverage.eligible is None:
        return "desconhecida"
    return f"{coverage.valid}/{coverage.eligible}"


def _fmt_metric(metric: Metric) -> str:
    if metric.ratio is not None:
        return _fmt_ratio(metric.ratio)
    if metric.quantity is None:
        return "—"
    return _fmt_quantity(metric.quantity)


def render_narrative_section(narrative: Narrative) -> str:
    """Seção de interpretação, sempre separada dos números e marcada como hipótese."""
    lines = [
        "",
        "## Interpretação (validada contra a execução)",
        "",
        "Hipóteses e ações abaixo não são fatos: cada uma cita a métrica ou a evidência que a",
        "sustenta e indica o que ainda precisa ser confirmado.",
        "",
    ]
    if narrative.hypotheses:
        lines.append("### Hipóteses")
        lines.append("")
        for hypothesis in narrative.hypotheses:
            references = ", ".join(hypothesis.references)
            lines.append(f"- {hypothesis.statement} (referências: {references})")
        lines.append("")
    if narrative.actions:
        lines.append("### Ações candidatas")
        lines.append("")
        for action in narrative.actions:
            references = ", ".join(action.references)
            lines.append(
                f"- {action.statement} — a confirmar: {action.condition_to_confirm} "
                f"(referências: {references})"
            )
        lines.append("")
    if narrative.rejected_fragments:
        lines.append(
            f"{len(narrative.rejected_fragments)} trechos foram descartados por não serem "
            "rastreáveis; veja `narrative.json`."
        )
        lines.append("")
    return "\n".join(lines)


def render_markdown(report: TeamReport) -> str:
    """Gera o Markdown do relatório de situação atual."""
    environment = Environment(
        loader=PackageLoader("ado_team_compass.reporting", "templates"),
        autoescape=select_autoescape(default=False, enabled_extensions=("html",)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    template = environment.get_template("report.md.j2")
    return template.render(
        report=report,
        fmt_quantity=_fmt_quantity,
        fmt_ratio=_fmt_ratio,
        fmt_coverage=_fmt_coverage,
        fmt_metric=_fmt_metric,
    )
