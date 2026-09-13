# ADO Team Compass

Visibilidade de entrega e orientação para o time, com base nos dados do Azure DevOps.

Plugin planejado para Claude Code, Google Antigravity e Codex (OpenAI/GPT), com motor Python independente, cálculos auditáveis e configuração adaptável a diferentes equipes.

## Canal exclusivo de acesso ao Azure DevOps

**Toda comunicação do ADO Team Compass com o Azure DevOps será realizada exclusivamente pelo [MCP oficial da Microsoft](https://github.com/microsoft/azure-devops-mcp).** Isso inclui descoberta, consultas, capacidade, histórico e qualquer futura ação autorizada.

O plugin não acessará diretamente APIs REST, Analytics/OData, SDKs ou CLI do ADO e não terá fallback de conexão direta. Python calcula e gera relatórios a partir das respostas do MCP. Recursos sem suporte no catálogo conectado ficam indisponíveis, com motivo explícito.

[Contrato de integração e cobertura do MCP](docs/ado-mcp-contract.md).

## Estado do projeto

Implementado e verificado localmente: as 28 tarefas do plano têm código, testes e documentação. O que **não** foi feito: conexão real com uma organização do Azure DevOps, instalação nos hosts em perfil limpo, piloto com equipes reais (T16) e implantação do gateway remoto (T28). Enquanto isso não acontecer, nomes de ferramenta do catálogo MCP, formatos de resposta e compatibilidade por host continuam **não verificados**.

| Release | Estado |
|---|---|
| v0.1 — situação atual, relatório e bundles | Código completo; falta handshake real, instalação em perfil limpo e piloto |
| v0.2 — histórico, compromisso, fluxo e planejamento | Código completo; falta reconciliação com equipe real |
| v0.3 — execução agendada | Código e templates completos; falta validar o modo não interativo em ambiente real |
| v0.3.1 — API para GPT personalizado | Código, OpenAPI e instruções completos; falta implantar e testar com Actions |
| v0.4 — forecast experimental | Código completo e rotulado experimental; falta calibração com dados reais |

```bash
uv sync --group dev && uv run pytest && uv run ado-team-compass version
```

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
- Integração de leitura exclusivamente pelo MCP oficial do Azure DevOps.

## Uso local

```bash
uv sync --group dev --extra api
uv run pytest
uv run ado-team-compass demo --format markdown
```

`demo` roda sem credencial e sem rede. Para dados reais: `setup`, `doctor` e `status`, com a sessão do MCP oficial já autenticada.

## Próximo passo

Tarefa T16: conectar o servidor MCP remoto oficial a uma organização real, registrar o catálogo efetivo e rodar o piloto descrito em [docs/piloto-v0.1.md](docs/piloto-v0.1.md).
