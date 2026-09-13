"""Regras de planejamento configuráveis por perfil (plano 4.1.5, T19).

Cada achado carrega regra e versão, severidade, item, evidência, a política que o motivou, a
exceção aplicável e a ação sugerida. Regras desabilitadas não produzem achado algum, e
nenhuma regra conclui produtividade: histórico de trabalho registrado não é timesheet.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date

from ado_team_compass.contracts.config import PlanningRule, StateCategory, TeamConfig
from ado_team_compass.contracts.facts import FactSet, WorkItemFact
from ado_team_compass.contracts.metrics import Finding

__all__ = [
    "DEFAULT_ENABLED",
    "RULES",
    "RuleContext",
    "RuleSpec",
    "enabled_rules",
    "evaluate_planning",
]

_CLOSED = (StateCategory.COMPLETED, StateCategory.REMOVED)


@dataclass(frozen=True)
class RuleContext:
    """Tudo que uma regra pode consultar. Nenhuma regra acessa rede ou relógio do sistema."""

    item: WorkItemFact
    facts: FactSet
    team: TeamConfig
    rule: PlanningRule
    today: date
    closed_iterations: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class RuleSpec:
    """Definição de uma regra: política, versão, severidade padrão e ação sugerida."""

    rule_id: str
    version: str
    default_enabled: bool
    default_severity: str
    policy: str
    suggested_action: str
    check: Callable[[RuleContext], str | None]


def _inverted_dates(context: RuleContext) -> str | None:
    item = context.item
    if item.start_date and item.target_date and item.start_date > item.target_date:
        return (
            f"a data de início {item.start_date.isoformat()} é posterior ao alvo "
            f"{item.target_date.isoformat()}"
        )
    return None


def _overdue_open_item(context: RuleContext) -> str | None:
    item = context.item
    if item.state_category is None or item.state_category in _CLOSED:
        return None
    if item.target_date is None:
        return None
    overdue_days = (context.today - item.target_date).days
    if overdue_days > context.rule.tolerance_days:
        return (
            f"o item continua aberto {overdue_days} dias após o alvo {item.target_date.isoformat()}"
        )
    return None


def _parent_ends_before_children(context: RuleContext) -> str | None:
    item, facts = context.item, context.facts
    if item.target_date is None:
        return None
    children_ids = {
        relation.child_id
        for relation in facts.relations
        if relation.parent_id == item.id and relation.relation == "hierarchy"
    }
    if not children_ids:
        return None
    late = [
        child
        for child in facts.items
        if child.id in children_ids
        and child.target_date is not None
        and child.target_date > item.target_date
    ]
    if not late:
        return None
    identifiers = ", ".join(str(child.id) for child in late)
    return (
        f"o alvo do pai é {item.target_date.isoformat()} e os filhos {identifiers} terminam "
        "depois disso"
    )


def _open_work_in_closed_sprint(context: RuleContext) -> str | None:
    item = context.item
    if item.state_category is None or item.state_category in _CLOSED:
        return None
    if item.iteration_path is None or not context.closed_iterations:
        return None
    if item.iteration_path not in context.closed_iterations:
        return None
    return f"o item segue aberto na iteração encerrada {item.iteration_path!r}"


def _missing_required_fields(context: RuleContext) -> str | None:
    item = context.item
    required = [name for name in context.rule.exceptions if name.startswith("require:")]
    missing = [
        name.removeprefix("require:")
        for name in required
        if getattr(item, name.removeprefix("require:"), None) in (None, "")
    ]
    if missing:
        return "campos exigidos pela política estão ausentes: " + ", ".join(missing)
    return None


def _story_without_task(context: RuleContext) -> str | None:
    item, facts, team = context.item, context.facts, context.team
    if team.process.accounting_level != "leaf_task":
        return None
    if item.item_type not in ("Product Backlog Item", "User Story"):
        return None
    has_child = any(relation.parent_id == item.id for relation in facts.relations)
    if has_child:
        return None
    return "o requisito não tem nenhuma task filha"


def _missing_estimate(context: RuleContext) -> str | None:
    item = context.item
    if item.state_category is None or item.state_category in _CLOSED:
        return None
    if item.remaining_work is not None and item.remaining_work.value is not None:
        return None
    return "o item aberto não tem trabalho restante registrado"


def _area_or_iteration_mismatch(context: RuleContext) -> str | None:
    item, team = context.item, context.team
    if not team.scope.area_paths or item.area_path is None:
        return None
    allowed = team.scope.area_paths
    if item.area_path in allowed:
        return None
    if team.scope.include_descendants and any(
        item.area_path.startswith(f"{area}\\") for area in allowed
    ):
        return None
    return f"a área {item.area_path!r} está fora do escopo configurado da equipe"


RULES: dict[str, RuleSpec] = {
    "inverted_dates": RuleSpec(
        rule_id="inverted_dates",
        version="1.0",
        default_enabled=True,
        default_severity="atencao",
        policy="datas de início e alvo precisam estar em ordem",
        suggested_action="corrigir as datas do item com quem o planejou",
        check=_inverted_dates,
    ),
    "overdue_open_item": RuleSpec(
        rule_id="overdue_open_item",
        version="1.0",
        default_enabled=True,
        default_severity="atencao",
        policy="item aberto não deve passar do alvo sem replanejamento",
        suggested_action="replanejar a data ou revisar o escopo do item",
        check=_overdue_open_item,
    ),
    "parent_ends_before_children": RuleSpec(
        rule_id="parent_ends_before_children",
        version="1.0",
        default_enabled=True,
        default_severity="atencao",
        policy="o alvo do pai não pode ser anterior ao dos filhos quando a política exige",
        suggested_action="alinhar as datas entre pai e filhos",
        check=_parent_ends_before_children,
    ),
    "open_work_in_closed_sprint": RuleSpec(
        rule_id="open_work_in_closed_sprint",
        version="1.0",
        default_enabled=True,
        default_severity="atencao",
        policy="trabalho aberto não deve permanecer em sprint encerrada",
        suggested_action="mover o item para a iteração corrente ou concluí-lo",
        check=_open_work_in_closed_sprint,
    ),
    "missing_required_fields": RuleSpec(
        rule_id="missing_required_fields",
        version="1.0",
        default_enabled=True,
        default_severity="info",
        policy="campos obrigatórios da política precisam estar preenchidos",
        suggested_action="preencher os campos exigidos pela política da equipe",
        check=_missing_required_fields,
    ),
    "story_without_task": RuleSpec(
        rule_id="story_without_task",
        version="1.0",
        default_enabled=False,
        default_severity="info",
        policy="requisito precisa ter task quando a equipe contabiliza por task folha",
        suggested_action="criar as tasks do requisito ou desativar esta regra",
        check=_story_without_task,
    ),
    "missing_estimate": RuleSpec(
        rule_id="missing_estimate",
        version="1.0",
        default_enabled=False,
        default_severity="info",
        policy="item aberto precisa de trabalho restante quando a equipe usa horas",
        suggested_action="estimar o trabalho restante; não imputar a estimativa original",
        check=_missing_estimate,
    ),
    "area_or_iteration_mismatch": RuleSpec(
        rule_id="area_or_iteration_mismatch",
        version="1.0",
        default_enabled=False,
        default_severity="info",
        policy="itens da equipe devem estar nas áreas configuradas",
        suggested_action="revisar a área do item ou o escopo configurado",
        check=_area_or_iteration_mismatch,
    ),
}

DEFAULT_ENABLED = tuple(sorted(spec.rule_id for spec in RULES.values() if spec.default_enabled))


def evaluate_planning(
    facts: FactSet,
    team: TeamConfig,
    *,
    today: date,
    rules: Mapping[str, PlanningRule] | None = None,
    closed_iterations: Sequence[str] = (),
) -> tuple[Finding, ...]:
    """Aplica apenas as regras habilitadas, na ordem estável de regra e item."""
    configured = dict(rules if rules is not None else team.planning.rules)
    findings: list[Finding] = []

    for rule_id in sorted(RULES):
        spec = RULES[rule_id]
        rule = configured.get(rule_id)
        if rule is None:
            if not spec.default_enabled:
                continue
            rule = PlanningRule(enabled=True, severity=spec.default_severity)
        if not rule.enabled:
            continue
        severity = rule.severity or spec.default_severity
        for item in sorted(facts.items, key=lambda entry: entry.id):
            if str(item.id) in rule.exceptions:
                continue
            detail = spec.check(
                RuleContext(
                    item=item,
                    facts=facts,
                    team=team,
                    rule=rule,
                    today=today,
                    closed_iterations=frozenset(closed_iterations),
                )
            )
            if detail is None:
                continue
            findings.append(
                Finding(
                    id=f"{spec.rule_id}:{item.id}",
                    rule_id=spec.rule_id,
                    rule_version=spec.version,
                    severity=severity,
                    message=f"Item {item.id}: {detail}. Política: {spec.policy}.",
                    item_ids=(item.id,),
                    evidence=(f"evidence/items/{item.id}.json",),
                    condition_to_confirm=spec.suggested_action,
                )
            )
    return tuple(findings)


def enabled_rules(team: TeamConfig) -> Sequence[str]:
    """Regras efetivamente ativas para a equipe, considerando perfil e overrides."""
    configured = team.planning.rules
    active: list[str] = []
    for rule_id, spec in sorted(RULES.items()):
        rule = configured.get(rule_id)
        if rule.enabled if rule is not None else spec.default_enabled:
            active.append(rule_id)
    return tuple(active)
