"""HTML operacional autocontido (T22, docs/sprint-report.md).

Regras do arquivo gerado:

- nenhum recurso externo: CSS, JavaScript e SVG ficam no próprio arquivo, sem CDN e sem
  requisição automática ao abrir;
- texto vindo do Azure DevOps é escapado: título malicioso não executa HTML ou JavaScript;
- todo gráfico tem tabela equivalente e legenda textual, e não depende só de cor;
- bloco sem dado suficiente explica a limitação em vez de mostrar zero ou gráfico fictício;
- o rascunho de decisões vive apenas na memória da página e precisa ser exportado.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from html import escape

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape
from markupsafe import Markup

from ado_team_compass.contracts.decisions import ActionCandidate
from ado_team_compass.contracts.facts import WorkItemFact
from ado_team_compass.contracts.report import TeamReport
from ado_team_compass.decisions import build_candidates
from ado_team_compass.reporting.markdown import (
    _fmt_coverage,
    _fmt_metric,
    _fmt_quantity,
    _fmt_ratio,
)

__all__ = ["render_html"]


@dataclass(frozen=True)
class _Card:
    label: str
    value: str
    note: str
    css_class: str = ""


def render_html(
    report: TeamReport,
    *,
    items: Sequence[WorkItemFact] = (),
    candidates: Sequence[ActionCandidate] | None = None,
) -> str:
    """Gera o relatório operacional offline a partir das mesmas métricas do JSON."""
    impediments = [item for item in items if item.blocked]
    resolved_candidates = (
        list(candidates)
        if candidates is not None
        else list(build_candidates(report, blocked_item_ids=tuple(item.id for item in impediments)))
    )
    gap = _gap(report)
    environment = Environment(
        loader=PackageLoader("ado_team_compass.reporting", "templates"),
        autoescape=select_autoescape(default_for_string=True, default=True),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = environment.get_template("report.html.j2")
    return template.render(
        report=report,
        context=_context(report),
        cards=_cards(report, gap, impediments),
        candidates=resolved_candidates,
        candidates_json=Markup(
            json.dumps(
                [candidate.model_dump(mode="json") for candidate in resolved_candidates],
                ensure_ascii=False,
            ).replace("<", "\\u003c")
        ),
        run_id_json=Markup(json.dumps(report.run_id, ensure_ascii=False).replace("<", "\\u003c")),
        gap=gap,
        impediments=[_safe_item(item) for item in impediments],
        classes=sorted({row.load_class for row in report.people}),
        fmt_quantity=_fmt_quantity,
        fmt_ratio=_fmt_ratio,
        fmt_coverage=_fmt_coverage,
        fmt_metric=_fmt_metric,
        capacity_svg=Markup(_capacity_svg(report, gap)),
    )


def _safe_item(item: WorkItemFact) -> dict[str, object]:
    """O título entra como excerto; o escape final é responsabilidade do template."""
    title = item.title or ""
    excerpt = title if len(title) <= 80 else title[:79] + "…"
    return {
        "id": item.id,
        "title": excerpt or None,
        "state": item.state,
        "assigned_to": item.assigned_to,
    }


def _context(report: TeamReport) -> dict[str, str]:
    remaining = "indisponível"
    people_with_capacity = [row for row in report.people if row.reserved_capacity is not None]
    capacity = report.metric("reserved_remaining_capacity")
    if capacity is not None and capacity.quantity and capacity.quantity.value is not None:
        remaining = _fmt_quantity(capacity.quantity)
    scope = report.iteration_path or "janela de análise"
    return {
        "remaining_days": remaining,
        "current_day_policy": "dia corrente conforme a política configurada",
        "scope": f"{scope} · {len(report.evidence_references)} itens observados · "
        f"{len(people_with_capacity)} pessoas com capacidade conhecida",
    }


@dataclass(frozen=True)
class _Gap:
    load: str
    load_note: str
    capacity: str
    capacity_note: str
    gap: str
    gap_note: str
    utilization: str
    utilization_note: str
    load_value: Decimal | None
    capacity_value: Decimal | None


def _gap(report: TeamReport) -> _Gap:
    load = report.metric("known_remaining_work")
    capacity = report.metric("reserved_remaining_capacity")
    utilization = report.metric("observed_utilization")
    load_value = load.quantity.value if load is not None and load.quantity is not None else None
    capacity_value = (
        capacity.quantity.value if capacity is not None and capacity.quantity is not None else None
    )
    partial = (
        load is not None
        and load.coverage.eligible is not None
        and load.coverage.valid < load.coverage.eligible
    )
    missing = load.quality.missing if load is not None else 0

    if load_value is not None and capacity_value is not None:
        difference = load_value - capacity_value
        unit = load.quantity.unit if load and load.quantity else report.unit
        gap_text = f"{'+' if difference > 0 else ''}{difference} {unit}"
        gap_note = (
            "gap conhecido: é um limite inferior porque há itens abertos sem estimativa"
            if partial
            else "diferença entre o trabalho conhecido e a reserva desta janela"
        )
        gap_note += "; não prevê data de atraso"
    else:
        gap_text = "indisponível"
        gap_note = "exige carga e capacidade conhecidas na mesma unidade e janela"

    return _Gap(
        load=_fmt_quantity(load.quantity) if load and load.quantity else "indisponível",
        load_note=(
            f"{missing} itens abertos sem trabalho restante" if missing else "cobertura completa"
        ),
        capacity=(
            _fmt_quantity(capacity.quantity) if capacity and capacity.quantity else "indisponível"
        ),
        capacity_note="soma das reservas conhecidas; reserva não é disponibilidade pessoal",
        gap=gap_text,
        gap_note=gap_note,
        utilization=_fmt_ratio(utilization.ratio) if utilization else "nulo",
        utilization_note=(
            "parcial: faltam estimativas"
            if partial
            else (utilization.unavailable_reason or "cobertura completa")
            if utilization
            else "indisponível"
        ),
        load_value=load_value,
        capacity_value=capacity_value,
    )


def _cards(report: TeamReport, gap: _Gap, impediments: Sequence[WorkItemFact]) -> list[_Card]:
    open_items = report.metric("open_items_count")
    blocked = report.metric("blocked_items_count")
    cards = [
        _Card(
            label="Objetivo da sprint",
            value="não informado",
            note="o objetivo vem de fonte configurada ou anotação humana; nunca é inventado",
        ),
        _Card(
            label="Itens abertos no escopo observado",
            value=_fmt_metric(open_items) if open_items else "indisponível",
            note="requisitos e tasks são contados conforme o nível de contabilização do perfil",
        ),
        _Card(
            label="Carga conhecida contra capacidade restante",
            value=f"{gap.load} / {gap.capacity}",
            note=gap.load_note,
        ),
        _Card(
            label="Gap de capacidade atual",
            value=gap.gap,
            note=gap.gap_note,
            css_class="ACIMA_DA_FAIXA"
            if gap.load_value is not None
            and gap.capacity_value is not None
            and gap.load_value > gap.capacity_value
            else "",
        ),
        _Card(
            label="Impedimentos ativos",
            value=str(len(impediments))
            if blocked is not None and blocked.status.value != "not_applicable"
            else "indisponível",
            note=(
                blocked.unavailable_reason
                or "itens marcados pela origem de impedimento configurada"
            )
            if blocked
            else "origem de impedimento não configurada",
        ),
        _Card(
            label="Mudanças de escopo",
            value="indisponível",
            note="exige baseline ou eventos históricos; entra na v0.2",
        ),
    ]
    return cards


def _capacity_svg(report: TeamReport, gap: _Gap) -> str:
    """Barras comparando carga conhecida e capacidade, com legenda textual e padrão visual."""
    if gap.load_value is None or gap.capacity_value is None:
        return (
            '<p class="indisponivel">Gráfico indisponível: carga e capacidade precisam estar '
            "conhecidas na mesma unidade e janela.</p>"
        )
    maximum = max(gap.load_value, gap.capacity_value) or Decimal(1)
    load_width = int(Decimal(420) * gap.load_value / maximum)
    capacity_width = int(Decimal(420) * gap.capacity_value / maximum)
    unit = escape(report.unit)
    title = (
        f"Carga conhecida {gap.load_value} {unit} e capacidade restante {gap.capacity_value} {unit}"
    )
    return f"""<figure>
<svg viewBox="0 0 520 120" width="520" height="120" role="img"
     aria-label="{escape(title)}">
  <defs>
    <pattern id="hachura" width="6" height="6" patternUnits="userSpaceOnUse"
             patternTransform="rotate(45)">
      <rect width="3" height="6" fill="currentColor" opacity="0.55"></rect>
    </pattern>
  </defs>
  <text x="0" y="16" font-size="12" fill="currentColor">Carga conhecida</text>
  <rect x="0" y="24" width="{load_width}" height="22" fill="url(#hachura)"
        stroke="currentColor"></rect>
  <text x="{load_width + 6}" y="40" font-size="12" fill="currentColor">
    {gap.load_value} {unit}</text>
  <text x="0" y="72" font-size="12" fill="currentColor">Capacidade restante</text>
  <rect x="0" y="80" width="{capacity_width}" height="22" fill="none"
        stroke="currentColor" stroke-width="2"></rect>
  <text x="{capacity_width + 6}" y="96" font-size="12" fill="currentColor">
    {gap.capacity_value} {unit}</text>
</svg>
<figcaption>{escape(title)}. A tabela abaixo traz os mesmos números.</figcaption>
</figure>"""
