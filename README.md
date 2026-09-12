# ADO Team Compass

Visibilidade de entrega e orientação para o time, com base nos dados do Azure DevOps.

Plugin planejado para Claude Code, com motor Python independente, cálculos auditáveis e configuração adaptável a diferentes equipes.

## Estado do projeto

Em planejamento. Este repositório contém a arquitetura e o plano de implementação; o plugin ainda não foi implementado.

## Planejamento

- [Plano de implementação](.memory-bank/plans/ado-team-compass/plan.md)
- [Arquitetura e decisões](.memory-bank/plans/ado-team-compass/architecture.md)
- [Checklist de 25 tarefas](.memory-bank/plans/ado-team-compass/task.md)

## Entregas previstas

| Versão | Escopo |
|---|---|
| v0.1 | Setup, diagnóstico, situação atual, carga condicional e distribuição |
| v0.2 | Histórico, métricas de fluxo e planejamento |
| v0.3 | Dashboard HTML e execução agendada |
| v0.4 | Forecast experimental com validação retrospectiva |

## Princípios

- Cálculos determinísticos separados da interpretação.
- Evidências e limitações explícitas por métrica.
- Configuração por perfil de equipe, sem impor horas ou sprints.
- Visão de carga sem ranking de produtividade individual.
- Integração de leitura com o Azure DevOps.

## Próximo passo

Iniciar a tarefa T01 do checklist: criar o pacote e a infraestrutura de qualidade.
