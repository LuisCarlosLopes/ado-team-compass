# Validação transversal — relatório de testes

Data: 13/09/2026. Cobre v0.1 a v0.4 implementadas. Este documento registra o que foi verificado automaticamente e o que
continua pendente de execução real. Nenhum item abaixo declara teste de produto que não tenha
sido executado.

## Como reproduzir

```bash
uv sync --group dev --extra api --frozen
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest
uv run python packaging/build_bundles.py --check
```

O conjunto padrão é determinístico: não usa rede, credencial nem relógio do sistema nos
cálculos. A integração real com uma organização é opt-in e fica fora do CI público.

## Cenários cobertos

| Cenário | Onde | Situação |
|---|---|---|
| V01, V12 — calendário, união de folgas, timezone e dia corrente | `tests/unit/test_calendar.py` | Coberto |
| V02, V03, V07, V09 — ausências, estimativa original, capacidade zero e hierarquia | `tests/unit/test_allocation.py` | Coberto |
| V04, V05, V06, V08 — consolidação entre equipes e unidades | `tests/unit/test_cross_team.py` | Coberto |
| V10, V13 — perfil sem horas e estados customizados | `tests/unit/test_quality.py`, `tests/unit/test_collect.py`, `tests/unit/test_setup.py` | Coberto |
| V11 — autenticação, permissão, limite, timeout e paginação | `tests/contract/test_mcp_client.py` | Coberto com respostas sintéticas |
| V14 — replay com entradas congeladas | `tests/unit/test_pipeline.py` | Coberto |
| V15, V16 — instrução em dado e referência inexistente | `tests/unit/test_html_report.py`, `tests/evals/test_narrative_validation.py` | Coberto |
| V25, V26 — paridade entre hosts e isolamento de bundles | `tests/install/test_bundles.py` | Coberto no pacote; instalação real pendente |
| V29, V30, V31, V32 — gap, variação indisponível, histórico ausente e decisões | `tests/unit/test_html_report.py` | Coberto |
| V33 — ausência de canal direto e bloqueio de escrita | `tests/contract/test_no_direct_ado_access.py`, `tests/contract/test_mcp_endpoint_policy.py` | Coberto |
| V17, V18, V19, V20 — baseline, reabertura, escopo e regras desligadas | `tests/unit/test_history.py`, `tests/unit/test_planning.py` | Coberto |
| V22 — agendamento simultâneo e falha posterior | `tests/integration/test_scheduled.py` | Coberto |
| V23, V24 — amostra insuficiente, semanas zeradas e backtesting | `tests/unit/test_forecast.py`, `tests/backtesting/` | Coberto |
| V27, V28 — autorização e atualidade no gateway | `tests/integration/test_gateway.py` | Coberto |
| Retenção de 30 dias e schema incompatível | `tests/integration/test_retention_and_schema.py` | Coberto |
| Verificação de segredos em artefatos, erros e logs | `tests/integration/test_secret_scan.py` | Coberto |

## Desempenho

Meta: fixture de 2.000 itens e 100 pessoas gera métricas e renderização em até 5 segundos,
offline. Verificado em `tests/integration/test_performance.py` para Markdown e HTML. O
executor de referência é o runner do CI (`ubuntu-latest`) e a máquina de desenvolvimento
registrada na execução. O tempo do servidor MCP oficial é medido à parte e não entra nesta
meta.

## Pendências que impedem declarar a v0.1 validada

1. Handshake real com o servidor MCP remoto oficial: os nomes de ferramenta usados vêm da
   documentação consultada e permanecem **não verificados** até a primeira conexão (T03/T04).
2. Instalação em perfil limpo nos três hosts, incluindo atualização e remoção (T15/T16).
3. Piloto com três equipes de perfis distintos, com reconciliação de uma amostra fixa de 20
   itens por equipe (T16).
4. Formatos reais de resposta do MCP para capacidade, folgas de equipe, iterações e revisões:
   a normalização é defensiva, mas só a conexão real confirma os campos.
5. Modo não interativo do MCP oficial para a coleta agendada (T23) e implantação do gateway
   com provedor OAuth corporativo e teste com GPT Actions (T28).
6. Calibração do forecast: ele permanece experimental até ter cobertura empírica medida sobre
   histórico real, e não deve embasar compromisso de prazo.
