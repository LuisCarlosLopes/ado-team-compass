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
from ado_team_compass.contracts.report import PersonRow, TeamReport
from ado_team_compass.decisions import build_candidates
from ado_team_compass.reporting.markdown import (
    _fmt_coverage,
    _fmt_decimal,
    _fmt_metric,
    _fmt_quantity,
    _fmt_ratio,
    _unit_label,
)

__all__ = ["render_html"]


@dataclass(frozen=True)
class _Verdict:
    """Frase de abertura escolhida pelos números, nunca escrita por modelo de linguagem."""

    tone: str  # acima | ok | indisponivel
    eyebrow: str
    headline: str
    subline: str


def _verdict(report: TeamReport, gap: _Gap, open_items: str) -> _Verdict:
    """Seleciona a frase a partir do estado das métricas; nada aqui é gerado."""
    load = report.metric("known_remaining_work")
    capacity = report.metric("reserved_remaining_capacity")
    not_applicable = {"not_applicable"}
    if (
        load is not None
        and capacity is not None
        and load.status.value in not_applicable
        and capacity.status.value in not_applicable
    ):
        return _Verdict(
            tone="indisponivel",
            eyebrow="O que dá para afirmar hoje",
            headline=(
                f"A janela tem {open_items} abertos. Carga e capacidade não se aplicam a "
                "esta equipe."
            ),
            subline=(
                "A equipe não registra trabalho restante nem mantém capacidade reservada: "
                "isso é a prática dela, não uma falha de preenchimento."
            ),
        )
    if gap.load_value is None or gap.capacity_value is None:
        return _Verdict(
            tone="indisponivel",
            eyebrow="O que dá para afirmar hoje",
            headline=f"A janela tem {open_items} abertos.",
            subline=(
                "Carga e capacidade não puderam ser comparadas nesta execução; o motivo de "
                "cada métrica está na tabela abaixo."
            ),
        )
    difference = gap.load_value - gap.capacity_value
    unit = _unit_label(report.unit)
    if difference > 0:
        return _Verdict(
            tone="acima",
            eyebrow="O que precisa de atenção hoje",
            headline="O trabalho conhecido não cabe na capacidade restante.",
            subline=(
                f"Restam {report.remaining_working_days} dias úteis na janela e há "
                f"{_fmt_decimal(gap.load_value)} {unit} de trabalho restante registrado "
                f"para {_fmt_decimal(gap.capacity_value)} {unit} de capacidade reservada."
            ),
        )
    if difference == 0:
        return _Verdict(
            tone="ok",
            eyebrow="O que os números dizem hoje",
            headline="O trabalho conhecido ocupa exatamente a capacidade restante.",
            subline=(
                f"{_fmt_decimal(gap.load_value)} {unit} de trabalho para "
                f"{_fmt_decimal(gap.capacity_value)} {unit} reservados, sem folga."
            ),
        )
    return _Verdict(
        tone="ok",
        eyebrow="O que os números dizem hoje",
        headline="O trabalho conhecido cabe na capacidade restante.",
        subline=(
            f"Sobram {_fmt_decimal(-difference)} {unit} de capacidade reservada depois do "
            f"trabalho registrado nesta janela."
        ),
    )


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
    open_items = report.metric("open_items_count")
    open_label = _fmt_metric(open_items) if open_items else "os itens"
    return template.render(
        people=[_person_view(row) for row in report.people],
        report=report,
        context=_context(report, gap),
        verdict=_verdict(report, gap, open_label),
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


def _person_view(row: PersonRow) -> dict[str, object]:
    """Linha da pessoa com uma barra proporcional opcional, descrita em texto."""
    bar: dict[str, object] | None = None
    load = row.known_load.value
    capacity = row.reserved_capacity.value if row.reserved_capacity else None
    if load is not None and capacity is not None and (load or capacity):
        total = max(load, capacity) or Decimal(1)
        fits = min(load, capacity)
        excess = max(Decimal(0), load - capacity)
        bar = {
            "fits": float(fits / total * 100),
            "excess": float(excess / total * 100),
            "label": (
                f"{_fmt_decimal(load)} {_unit_label(row.known_load.unit)} de carga contra "
                f"{_fmt_decimal(capacity)} {_unit_label(row.known_load.unit)} de capacidade"
            ),
        }
    payload = row.model_dump(mode="json")
    payload["bar"] = bar
    payload["known_load"] = row.known_load
    payload["reserved_capacity"] = row.reserved_capacity
    payload["utilization"] = row.utilization
    return payload


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


def _context(report: TeamReport, gap: _Gap) -> dict[str, str]:
    """Rótulos derivados do relatório; nenhum texto aqui inventa número."""
    load = report.metric("known_remaining_work")
    missing = load.quality.missing if load is not None else 0
    lower_bound = ""
    if missing:
        lower_bound = (
            f"{missing} item(ns) aberto(s) sem trabalho restante registrado, então o total "
            "real pode ser maior — nunca menor."
        )
    window_label = ""
    if report.window is not None:
        window_label = (
            f"{report.window.start.date().isoformat()} a "
            f"{report.window.end.date().isoformat()} (fim exclusivo, {report.window.timezone})"
        )
    if gap.load_value is not None and gap.capacity_value is not None:
        if gap.load_value < gap.capacity_value:
            gap_label = "de folga na reserva"
        elif gap.load_value == gap.capacity_value:
            gap_label = "de diferença"
        else:
            gap_label = "além da capacidade"
    else:
        gap_label = "sem comparação possível nesta execução"
    return {
        "window_label": window_label,
        "gap_label": gap_label,
        "lower_bound": lower_bound,
        "current_day_policy": "dia corrente conforme a política configurada",
        "evidence": f"{len(report.evidence_references)} itens com evidência",
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
        gap_text = f"{'+' if difference > 0 else ''}{_fmt_decimal(difference)} {_unit_label(unit)}"
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
    """Quatro fatos do escopo observado, na ordem em que a leitura precisa deles."""
    open_items = report.metric("open_items_count")
    blocked = report.metric("blocked_items_count")
    load = report.metric("known_remaining_work")
    accountable = open_items.coverage.eligible if open_items else None
    missing_count = load.quality.missing if load is not None else 0

    cards = [
        _Card(
            label="Itens abertos",
            value=_fmt_metric(open_items) if open_items else "indisponível",
            note=(
                f"de {accountable} contabilizados no nível do perfil"
                if accountable is not None
                else "conforme o nível de contabilização do perfil"
            ),
        )
    ]
    if blocked is not None and blocked.status.value == "not_applicable":
        cards.append(
            _Card(
                label="Impedimentos",
                value="não aplicável",
                note=blocked.unavailable_reason or "origem de impedimento não configurada",
                css_class="DADOS_INSUFICIENTES",
            )
        )
    else:
        identifiers = ", ".join(str(item.id) for item in impediments[:3])
        cards.append(
            _Card(
                label="Impedimentos",
                value=str(len(impediments)),
                note=f"itens {identifiers}" if identifiers else "nenhum item marcado",
                css_class="ACIMA_DA_FAIXA" if impediments else "",
            )
        )
    if load is not None and load.status.value == "not_applicable":
        cards.append(
            _Card(
                label="Carga registrada",
                value="não aplicável",
                note=load.unavailable_reason or "a equipe não registra trabalho restante",
                css_class="DADOS_INSUFICIENTES",
            )
        )
    else:
        cards.append(
            _Card(
                label="Sem estimativa",
                value=str(missing_count),
                note=(
                    "itens abertos que tornam a carga um limite inferior"
                    if missing_count
                    else "todo item aberto tem trabalho restante registrado"
                ),
                css_class="ATENCAO" if missing_count else "",
            )
        )
    cards.append(
        _Card(
            label="Objetivo da sprint",
            value="não informado",
            note="vem de fonte configurada ou anotação humana; nunca é inventado",
            css_class="DADOS_INSUFICIENTES",
        )
    )
    return cards


def _capacity_svg(report: TeamReport, gap: _Gap) -> str:
    """Barra proporcional: o que cabe na reserva, o que excede e a folga.

    O excedente é hachurado além de colorido, para não depender de cor, e os mesmos números
    aparecem na tabela de capacidade.
    """
    if gap.load_value is None or gap.capacity_value is None:
        return (
            '<p class="indisponivel">Sem barra de carga: esta execução não tem carga e '
            "capacidade conhecidas na mesma unidade e janela.</p>"
        )
    total = max(gap.load_value, gap.capacity_value) or Decimal(1)
    width = Decimal(880)
    fits = min(gap.load_value, gap.capacity_value)
    excess = max(Decimal(0), gap.load_value - gap.capacity_value)
    slack = max(Decimal(0), gap.capacity_value - gap.load_value)
    fits_width = int(width * fits / total)
    excess_width = int(width * excess / total)
    slack_width = int(width * slack / total)
    unit = _unit_label(report.unit)
    title = (
        f"Carga conhecida {_fmt_decimal(gap.load_value)} {unit} contra capacidade restante "
        f"reservada {_fmt_decimal(gap.capacity_value)} {unit}"
    )
    blocks = [
        f'<rect x="0" y="0" width="{fits_width}" height="46" class="cabe"></rect>',
        f'<text x="{max(46, fits_width // 2)}" y="29" class="rotulo-barra" '
        f'text-anchor="middle">{escape(_fmt_decimal(fits))} {escape(unit)}</text>',
    ]
    if excess_width:
        middle = fits_width + excess_width // 2
        blocks.append(
            f'<rect x="{fits_width}" y="0" width="{excess_width}" height="46" '
            'class="excede" fill="url(#hachura)"></rect>'
        )
        blocks.append(
            f'<text x="{middle}" y="29" class="rotulo-excede" text-anchor="middle">'
            f"{escape(_fmt_decimal(excess))} {escape(unit)} sem capacidade correspondente</text>"
        )
    if slack_width:
        middle = fits_width + slack_width // 2
        blocks.append(
            f'<rect x="{fits_width}" y="0" width="{slack_width}" height="46" '
            'class="folga-reserva"></rect>'
        )
        blocks.append(
            f'<text x="{middle}" y="29" class="rotulo-folga" text-anchor="middle">'
            f"{escape(_fmt_decimal(slack))} {escape(unit)} de folga na reserva</text>"
        )
    return f"""<figure class="barra">
<svg viewBox="0 0 880 46" width="100%" height="46" preserveAspectRatio="none" role="img"
     aria-label="{escape(title)}">
  <defs>
    <pattern id="hachura" width="10" height="10" patternUnits="userSpaceOnUse"
             patternTransform="rotate(135)">
      <rect width="5" height="10" fill="currentColor" opacity="0.30"></rect>
    </pattern>
  </defs>
  {"".join(blocks)}
</svg>
<figcaption>{escape(title)}. A tabela abaixo traz os mesmos números.</figcaption>
</figure>"""
