"""Carga conhecida, exclusões e classificação local de carga (plano 4.1.4).

Regras implementadas:

- ausência de trabalho restante não vira zero e `OriginalEstimate` nunca o substitui;
- valor negativo é inválido, sai da soma e gera achado;
- item concluído com trabalho restante positivo é inconsistência, não entra na carga aberta;
- pai e filho nunca entram na mesma soma: vale um único nível de contabilização;
- utilização usa a mesma janela e a mesma unidade do numerador;
- dados incompletos impedem classificação de carga baixa.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from ado_team_compass.contracts.common import QualityCounters, Quantity
from ado_team_compass.contracts.config import StateCategory, Thresholds
from ado_team_compass.contracts.facts import WorkItemFact, WorkItemRelation
from ado_team_compass.contracts.metrics import Finding

__all__ = [
    "CLOSED_CATEGORIES",
    "DEFAULT_THRESHOLDS",
    "Classification",
    "KnownLoad",
    "LoadClass",
    "accountable_items",
    "classify_load",
    "known_load",
]

CLOSED_CATEGORIES = (StateCategory.COMPLETED, StateCategory.REMOVED)

#: Limiares padrão do produto; perfis e equipes podem substituí-los na configuração.
DEFAULT_THRESHOLDS = Thresholds()


class LoadClass(StrEnum):
    """Classes padrão de carga; nenhuma delas afirma ociosidade real."""

    SEM_CARGA_REGISTRADA = "SEM_CARGA_REGISTRADA"
    ABAIXO_DA_FAIXA = "ABAIXO_DA_FAIXA"
    DENTRO_DA_FAIXA = "DENTRO_DA_FAIXA"
    ATENCAO = "ATENCAO"
    ACIMA_DA_FAIXA = "ACIMA_DA_FAIXA"
    DADOS_INSUFICIENTES = "DADOS_INSUFICIENTES"
    CARGA_SEM_CAPACIDADE = "CARGA_SEM_CAPACIDADE"


@dataclass(frozen=True)
class KnownLoad:
    """Carga conhecida de um recorte, com contadores de qualidade e achados."""

    quantity: Quantity
    counters: QualityCounters
    findings: tuple[Finding, ...] = ()

    @property
    def is_complete(self) -> bool:
        """Completa quando todo item elegível tem valor válido conhecido."""
        return self.counters.eligible is not None and self.counters.known == self.counters.eligible


@dataclass(frozen=True)
class Classification:
    """Classe de carga, razão observada e motivo quando não há percentual."""

    load_class: LoadClass
    ratio: Decimal | None
    reason: str | None = None
    is_lower_bound: bool = False


def accountable_items(
    items: Sequence[WorkItemFact],
    relations: Iterable[WorkItemRelation] = (),
    *,
    accounting_level: str | None = None,
) -> tuple[WorkItemFact, ...]:
    """Seleciona um único nível de contabilização para impedir soma de pai e filho."""
    hierarchy = [relation for relation in relations if relation.relation == "hierarchy"]
    parents = {relation.parent_id for relation in hierarchy}
    children = {relation.child_id for relation in hierarchy}
    if accounting_level == "leaf_task":
        return tuple(item for item in items if item.id not in parents)
    if accounting_level == "requirement":
        return tuple(item for item in items if item.id not in children)
    return tuple(items)


def known_load(
    items: Sequence[WorkItemFact],
    *,
    unit: str,
    relations: Iterable[WorkItemRelation] = (),
    accounting_level: str | None = None,
) -> KnownLoad:
    """Soma o trabalho restante válido dos itens abertos elegíveis do nível contabilizado."""
    eligible = accountable_items(items, relations, accounting_level=accounting_level)
    total = Quantity(value=None, unit=unit)
    known = missing = invalid = excluded = 0
    reasons: list[str] = []
    findings: list[Finding] = []
    counted = 0

    for item in eligible:
        if item.state_category is None:
            excluded += 1
            reasons.append(f"item {item.id} tem estado {item.state!r} sem categoria mapeada")
            findings.append(
                _finding(
                    "unmapped_state",
                    "atencao",
                    f"O estado {item.state!r} do item {item.id} não está mapeado; "
                    "métricas dependentes ficam indisponíveis para ele.",
                    item.id,
                    "mapear o estado em process.state_categories",
                )
            )
            continue
        if item.state_category in CLOSED_CATEGORIES:
            remaining = item.remaining_work
            if remaining is not None and remaining.value is not None and remaining.value > 0:
                excluded += 1
                reasons.append(f"item {item.id} está concluído com trabalho restante positivo")
                findings.append(
                    _finding(
                        "completed_with_remaining_work",
                        "atencao",
                        f"O item {item.id} está em estado concluído e mantém trabalho "
                        "restante positivo; ele não entra na carga aberta.",
                        item.id,
                        "confirmar com a equipe se o item foi realmente concluído",
                    )
                )
            continue

        counted += 1
        remaining = item.remaining_work
        if remaining is None or remaining.value is None:
            missing += 1
            reasons.append(f"item {item.id} aberto sem trabalho restante registrado")
            continue
        if remaining.unit != unit:
            invalid += 1
            reasons.append(
                f"item {item.id} usa unidade {remaining.unit!r}, incompatível com {unit!r}"
            )
            continue
        if remaining.value < 0:
            invalid += 1
            reasons.append(f"item {item.id} tem trabalho restante negativo")
            findings.append(
                _finding(
                    "negative_remaining_work",
                    "atencao",
                    f"O item {item.id} tem trabalho restante negativo e foi excluído da soma.",
                    item.id,
                    "corrigir o valor no item antes de comparar com a capacidade",
                )
            )
            continue
        known += 1
        total = total.add(remaining)

    counters = QualityCounters(
        eligible=counted,
        known=known,
        missing=missing,
        invalid=invalid,
        excluded=excluded,
        reasons=tuple(dict.fromkeys(reasons)),
    )
    if known == 0:
        total = Quantity(value=None, unit=unit)
    return KnownLoad(quantity=total, counters=counters, findings=tuple(findings))


def _finding(rule_id: str, severity: str, message: str, item_id: int, condition: str) -> Finding:
    return Finding(
        id=f"{rule_id}:{item_id}",
        rule_id=rule_id,
        rule_version="1.0",
        severity=severity,
        message=message,
        item_ids=(item_id,),
        evidence=(f"evidence/items/{item_id}",),
        condition_to_confirm=condition,
    )


def classify_load(
    load: KnownLoad,
    capacity: Quantity | None,
    *,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> Classification:
    """Classifica carga contra capacidade restante reservada, na mesma unidade e janela."""
    load_value = load.quantity.value
    if capacity is not None and capacity.unit != load.quantity.unit:
        return Classification(
            LoadClass.DADOS_INSUFICIENTES,
            None,
            reason=(
                f"carga em {load.quantity.unit!r} e capacidade em {capacity.unit!r} não são "
                "comparáveis sem fator explícito"
            ),
        )
    if capacity is None or capacity.value is None:
        return Classification(
            LoadClass.DADOS_INSUFICIENTES,
            None,
            reason="capacidade restante reservada desconhecida para a janela",
            is_lower_bound=load_value is not None and load_value > 0,
        )
    if load_value is None:
        if load.counters.eligible == 0:
            return Classification(
                LoadClass.SEM_CARGA_REGISTRADA,
                None,
                reason="nenhum item aberto elegível no recorte",
            )
        return Classification(
            LoadClass.DADOS_INSUFICIENTES,
            None,
            reason="nenhum item aberto possui trabalho restante conhecido",
        )
    if capacity.value == 0:
        if load_value == 0:
            return Classification(
                LoadClass.SEM_CARGA_REGISTRADA,
                None,
                reason="capacidade zero e carga zero não produzem percentual",
            )
        return Classification(
            LoadClass.CARGA_SEM_CAPACIDADE,
            None,
            reason="há carga conhecida sem capacidade restante reservada",
            is_lower_bound=not load.is_complete,
        )

    ratio = load_value / capacity.value
    if not load.is_complete:
        # Dados incompletos nunca sustentam classificação de carga baixa; sobrecarga já
        # demonstrada pela carga conhecida permanece visível como limite inferior.
        if ratio > thresholds.attention:
            return Classification(
                LoadClass.ACIMA_DA_FAIXA,
                ratio,
                reason="percentual parcial: há itens abertos sem trabalho restante",
                is_lower_bound=True,
            )
        return Classification(
            LoadClass.DADOS_INSUFICIENTES,
            ratio,
            reason="percentual parcial: há itens abertos sem trabalho restante",
            is_lower_bound=True,
        )
    if load_value == 0:
        return Classification(
            LoadClass.SEM_CARGA_REGISTRADA, ratio, reason="carga conhecida igual a zero"
        )
    if ratio < thresholds.below_range:
        return Classification(LoadClass.ABAIXO_DA_FAIXA, ratio)
    if ratio <= thresholds.within_range:
        return Classification(LoadClass.DENTRO_DA_FAIXA, ratio)
    if ratio <= thresholds.attention:
        return Classification(LoadClass.ATENCAO, ratio)
    return Classification(LoadClass.ACIMA_DA_FAIXA, ratio)
