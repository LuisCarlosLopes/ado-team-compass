# ADO Team Compass

Visibilidade de entrega e orientação para o time, com base nos dados do Azure DevOps.

Plugin planejado para Claude Code, Google Antigravity e Codex (OpenAI/GPT), com motor Python independente, cálculos auditáveis e configuração adaptável a diferentes equipes.

## Estado do projeto

Em planejamento. Este repositório contém a arquitetura e o plano de implementação; o plugin ainda não foi implementado.

## Planejamento

- [Plano de implementação](.memory-bank/plans/ado-team-compass/plan.md)
- [Arquitetura e decisões](.memory-bank/plans/ado-team-compass/architecture.md)
- [Checklist de 28 tarefas](.memory-bank/plans/ado-team-compass/task.md)

## Compatibilidade planejada

| Ambiente | Integração | Release |
|---|---|---|
| Claude Code | Plugin e skills locais | v0.1 |
| Google Antigravity IDE | Bundle próprio com skills | v0.1 |
| Codex / GPT no Codex | Bundle Codex com skills locais | v0.1 |
| GPT personalizado no ChatGPT | Actions com API HTTPS autenticada | v0.3.1 |

A compatibilidade é parte do plano, ainda não foi implementada ou testada. GPT personalizado exige um serviço remoto; instalar o bundle local não disponibiliza esse serviço.

[Formatos, limites e testes por plataforma](docs/platform-compatibility.md).

## Entregas previstas

| Versão | Escopo |
|---|---|
| v0.1 | Relatório HTML de sprint, entrega, carga/capacidade, gap, impedimentos e ações recomendadas; distribuição para três hosts locais |
| v0.2 | Burnup/burndown, baseline de horas, desvios por coorte, métricas de fluxo e planejamento |
| v0.3 | Execução agendada e operação dos relatórios |
| v0.3.1 | API autenticada e GPT Actions para consulta remota |
| v0.4 | Forecast experimental com validação retrospectiva |

## Relatório HTML de gestão

A primeira versão prevê entrega atual, planejamento de capacidade, carga restante conhecida, gap, impedimentos, gargalos indicados por evidências e ações recomendadas. Filtros e exportação/importação de decisões apoiam o acompanhamento. Histórico e desvios que dependem de baseline entram na v0.2; o relatório não inventa dados ausentes nem executa alterações no ADO.

[Especificação do relatório e indicadores prioritários](docs/sprint-report.md).

## Princípios

- Cálculos determinísticos separados da interpretação.
- Evidências e limitações explícitas por métrica.
- Configuração por perfil de equipe, sem impor horas ou sprints.
- Visão de carga sem ranking de produtividade individual.
- Integração de leitura com o Azure DevOps.

## Próximo passo

Iniciar a tarefa T01 do checklist: criar o pacote e a infraestrutura de qualidade.
