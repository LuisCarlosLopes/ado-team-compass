"""Rótulos legíveis para apresentação humana de identificadores técnicos."""

from __future__ import annotations

__all__ = [
    "METRIC_LABELS",
    "PROCESS_FIELD_LABELS",
    "field_label",
    "metric_label",
    "process_field_label",
]

#: Nomes amigáveis das métricas em português (conforme docs/sprint-report.md).
METRIC_LABELS: dict[str, str] = {
    "open_items_count": "Itens abertos",
    "blocked_items_count": "Impedimentos ativos",
    "known_remaining_work": "Carga restante conhecida",
    "reserved_remaining_capacity": "Capacidade restante reservada",
    "observed_utilization": "Utilização observada",
}

#: Rótulos legíveis das chaves de configuração de processo da equipe.
PROCESS_FIELD_LABELS: dict[str, str] = {
    "remaining_work_field": "trabalho restante",
    "original_estimate_field": "estimativa original",
    "completed_work_field": "trabalho realizado",
    "story_points_field": "pontos de história",
    "impediment_source": "origem de impedimento",
    "blocked_states": "estados de bloqueio",
    "accounting_level": "nível de contabilização",
    "sprint_goal_source": "origem do objetivo da sprint",
    "state_categories": "categorias de estado",
    "wip_limits": "limites de WIP",
}


def field_label(name: str) -> str:
    """Remove qualquer namespace pontuado do nome de um campo.

    Exemplos:
        Microsoft.VSTS.Scheduling.RemainingWork -> RemainingWork
        System.Tags -> Tags
        RemainingWork -> RemainingWork
    """
    if "." in name:
        return name.rsplit(".", 1)[-1]
    return name


def metric_label(metric_id: str) -> str:
    """Retorna o rótulo amigável em pt-BR da métrica, com fallback para o próprio ID."""
    return METRIC_LABELS.get(metric_id, metric_id)


def process_field_label(config_key: str) -> str:
    """Retorna o rótulo legível da chave de configuração de processo."""
    return PROCESS_FIELD_LABELS.get(config_key, config_key)
