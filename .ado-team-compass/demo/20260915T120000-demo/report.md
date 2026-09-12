# Situação atual — demo

| Campo | Valor |
|---|---|
| Execução | `20260915T120000-demo` |
| Equipe | `team-demo` (projeto `proj-demo`) |
| Perfil | sprint_with_capacity |
| Instante de referência | 2026-09-15T12:00:00-03:00 |
| Janela | 2026-09-14T00:00:00-03:00 até 2026-09-19T00:00:00-03:00 (fim exclusivo, America/Sao_Paulo) |
| Iteração | Demo\Sprint 42 |
| Unidade | hours |

## Métricas

| Métrica | Status | Valor | Cobertura de itens | Motivo |
|---|---|---|---|---|
| `open_items_count` | available | 6 items | 8/8 | — |
| `blocked_items_count` | available | 1 items | 8/8 | — |
| `known_remaining_work` | partial | 28 hours | 4/6 | — |
| `reserved_remaining_capacity` | available | 30 hours | 2/2 | — |
| `observed_utilization` | partial | 93.3% | 4/6 | — |

## Carga conhecida por pessoa

| Pessoa | Carga conhecida | Capacidade restante | Utilização | Classe | Itens (elegíveis/conhecidos/ausentes) |
|---|---|---|---|---|---|
| `person-ana` | 18 hours | 12 hours | 150.0% (limite inferior) | ACIMA_DA_FAIXA | 3/2/1 |
| `person-bruno` | 10 hours | 18 hours | 55.6% (limite inferior) | DADOS_INSUFICIENTES | 3/2/1 |

## Achados

- **atencao** · `unmapped_state` — O estado 'Em análise' do item 108 não está mapeado; métricas dependentes ficam indisponíveis para ele.
  - Itens: 108
  - Evidência: evidence/items/108.json
  - A confirmar: mapear o estado em process.state_categories

## Limitações e cobertura

Fontes parciais: team_days_off.

- item 105: sem valor em Microsoft.VSTS.Scheduling.RemainingWork
- item 106: sem valor em Microsoft.VSTS.Scheduling.RemainingWork
- item 108: estado 'Em análise' sem categoria mapeada
- folgas da equipe não vieram na resposta do MCP
- classe DADOS_INSUFICIENTES: percentual parcial: há itens abertos sem trabalho restante

## Evidências

9 itens com evidência minimizada em `evidence/items/`.
Cada total desta página é reconciliável pelas métricas em `metrics.json` e por essas evidências.

Nenhum número desta página foi produzido por modelo de linguagem. Ausência de registro não
é ociosidade, e a classe de carga não mede produtividade individual.
