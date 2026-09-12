# Relatório HTML de sprint e apoio à decisão — v1.3

Estado: especificação de produto; HTML ainda não implementado. Data: 12/09/2026. Este documento amplia T22 e antecipa o relatório operacional para a v0.1. Histórico e comparações que dependem de dados passados entram progressivamente na v0.2.

**Origem obrigatória:** todos os dados ADO usados neste relatório chegam exclusivamente pelo [MCP oficial Microsoft](https://github.com/microsoft/azure-devops-mcp). Configurações e decisões humanas têm proveniência distinta. Sem ferramenta/cobertura no MCP, o indicador é indisponível ou parcial; nunca haverá fallback REST/OData direto. [Contrato](ado-mcp-contract.md).

## 1. Decisões que o relatório deve apoiar

1. O objetivo da sprint está ameaçado e por quais entregas?
2. O trabalho conhecido cabe na capacidade restante, na janela e atividade certas?
3. O que mudou no escopo ou na estimativa e o que explica o desvio?
4. Onde o trabalho está esperando, bloqueado ou acumulando?
5. Qual decisão precisa ser tomada agora, por quem e com quais evidências?

O objetivo da sprint vem de fonte explícita configurada ou anotação humana; nunca é inventado a partir de títulos. Sua situação pode ter avaliação humana e sinais automáticos separados. “Sem risco detectado” não significa “entrega garantida”. O Scrum Guide coloca a inspeção do progresso em direção ao objetivo e a adaptação do plano no centro do Daily Scrum. [Scrum Guide](https://scrumguides.org/scrum-guide.html).

## 2. Hierarquia visual

O HTML será um documento autocontido, com SVG e JavaScript local mínimo para filtros, ordenação e detalhes. Sem CDN, chamadas externas automáticas ou exposição de dados no navegador. Links ADO são ações de navegação explícitas, nunca requisições disparadas ao abrir o arquivo.

### Faixa de contexto

Equipe, sprint/janela, objetivo, período, data de referência, última coleta, dias úteis restantes, política do dia atual e escopo observado. Sempre mostrar se o relatório é parcial ou antigo. Para Kanban, trocar o cabeçalho de sprint por janela de análise.

### Visão executiva: “O que precisa de atenção hoje”

Até cinco sinais prioritários e três decisões sugeridas. Cada sinal mostra número, unidade, cobertura e link para detalhes. Não usar um score de saúde universal que esconda problemas distintos.

Cartões prioritários:

| Cartão | Pergunta | Quando habilitar |
|---|---|---|
| Objetivo e entregas críticas | O que não pode ficar para trás? | Objetivo e vínculo explícitos; senão pedir registro |
| Entregues / em andamento / não iniciados | Qual é a situação do escopo observado? | Tipos e estados mapeados |
| Carga conhecida versus capacidade restante | Cabe o trabalho registrado? | Mesma unidade e janela; qualidade por métrica |
| Impedimentos ativos | O que está bloqueando a entrega? | Campo, tag ou relação configurada como evidência |
| Mudanças de escopo | Entrou trabalho após o compromisso? | Baseline/eventos disponíveis |

Não acrescentar dezenas de cartões acima da primeira tabela. Informações de configuração, qualidade e histórico ficam acessíveis sem competir com decisões prioritárias.

### Entrega e escopo

Tabela de requisitos com prioridade configurada, vínculo ao objetivo, estado, responsável, prazo, impedimento e evidência. Contar requisitos e tasks separadamente; nunca chamar 80% de tasks fechadas de 80% de valor entregue.

Na v0.2: burnup de entregas e escopo, mostrando baseline, entradas e saídas. Burndown de horas será complementar para equipes que mantêm horas restantes. A Microsoft distingue mudança de escopo do consumo de trabalho nos gráficos de sprint; por isso uma linha de restante isolada não basta para explicar desvio. [Burndown de sprint](https://learn.microsoft.com/en-us/azure/Devops/report/dashboards/configure-sprint-burndown?view=azure-devops).

Sem histórico, apresentar tabela atual e aviso de série indisponível. Não preencher dias passados por interpolação como se fossem observados.

### Planejamento de horas e desvios

Exibir por equipe, atividade e, em detalhes, pessoa: capacidade total/ restante, carga restante conhecida, itens sem estimativa, horas registradas quando válidas, variação e cobertura. Mostrar carga sem responsável em linha separada; ela continua fazendo parte da carga da equipe.

Quatro medidas diferentes precisam de nomes próprios:

| Medida | Cálculo e interpretação |
|---|---|
| Gap de capacidade atual | Trabalho restante conhecido − capacidade restante; positivo sugere necessidade de ajuste, sem prever data |
| Utilização observada | Restante conhecido / capacidade restante; parcial se faltam estimativas |
| Variação da estimativa total | Estimativa atual de conclusão − estimativa congelada da mesma coorte; exige baseline compatível |
| Desvio final registrado | Trabalho realizado registrado ao final − estimativa da baseline; exige prática confiável de registro |

Para estimativa atual de conclusão, `CompletedWork + RemainingWork` só é permitido quando o perfil confirmar que esses campos são completos, comparáveis e relativos à mesma coorte/período. Não usar como medição automática de tempo trabalhado. Se o item atravessa sprints, `CompletedWork` acumulado não pode ser atribuído integralmente à sprint atual. Sem histórico/corte adequado, exibir indisponível.

Separar efeitos: escopo adicionado, escopo removido, reestimativa dos itens que permanecem e mudança de capacidade. Não atribuir todo desvio ao time. Percentual com baseline zero é nulo; valor absoluto pode continuar visível.

**Exemplo sintético:** capacidade restante 120 h, restante conhecido 144 h e três tasks sem restante: gap conhecido de +24 h, utilização observada de 120% e carga incompleta. Isso já indica incompatibilidade entre trabalho conhecido e reserva, mas não autoriza estimar o total das três tasks nem dizer quantos dias a sprint atrasará.

### Fluxo, gargalos e impedimentos

| Sinal | Evidência necessária | Limite da conclusão |
|---|---|---|
| Bloqueado explicitamente | Campo/tag/relação configurada | Ausência de registro não prova ausência de impedimento |
| Duração do impedimento | Evento de início/fim ou data informada | Última alteração genérica não define início do bloqueio |
| Espera em etapa | Histórico de coluna/estado que represente fila | Sem histórico, mostrar apenas quantidade atual |
| WIP acima do limite | Contagem atual e limite configurado | É violação de política, não causa demonstrada |
| Aging acima da referência | Início do episódio e referência do perfil/coorte | Item antigo não implica inatividade da pessoa |
| Déficit de atividade | Carga e capacidade compatíveis por atividade | Mostra desequilíbrio estimado, não gargalo garantido |
| Dependência externa aberta | Relação e estado do predecessor | Não assumir todas as relações como bloqueantes |

Acúmulo persistente em uma etapa é indício mais forte que uma fotografia isolada. CFD e histórico de tempos entram na v0.2, com coortes explícitas; não exigir um CFD para a v0.1 ser útil. A orientação do Azure Boards relaciona WIP, tempo de ciclo e leitura de gargalos, mas a causalidade precisa de investigação. [Orientação de fluxo](https://learn.microsoft.com/en-us/azure/devops/report/dashboards/cumulative-flow-cycle-lead-time-guidance?view=azure-devops).

Tabela de impedimentos: item, entrega afetada, evidência, desde quando (ou desconhecido), responsável pelo item, responsável pela resolução quando registrado, dependência, próximo passo e link. Não inventar o responsável pela resolução a partir do AssignedTo.

## 3. Recomendações que levam a uma decisão

O núcleo gera candidatos determinísticos com referências; o LLM pode contextualizar, sem mudar fatos. Ordenação explícita: ameaça demonstrada a entrega vinculada ao objetivo → impedimento/prazo próximo → déficit conhecido de capacidade → fila acima do limite → falta de dados que impede decisão. Empates usam severidade configurada, prazo conhecido e ID estável. Prioridade desconhecida não vira baixa prioridade.

| Situação | Ação candidata | Condição para decidir |
|---|---|---|
| Carga acima da capacidade | Negociar escopo, fatiar entrega ou redistribuir | Validar dependências, habilidades e prioridade |
| Bloqueio em entrega crítica | Acionar responsável registrado pela resolução | Confirmar vínculo com objetivo e causa do bloqueio |
| Fila acima de WIP | Priorizar conclusão/desbloqueio antes de iniciar mais | Conferir política e contexto da fila |
| Trabalho novo compromete reserva | Explicitar troca de escopo com responsável do produto | Identificar o que sai ou qual objetivo muda |
| Restante ausente | Atualizar estimativa dos itens listados | Não imputar OriginalEstimate |
| Sem carga registrada | Verificar trabalho fora do board e disponibilidade | Não concluir ociosidade nem reatribuir automaticamente |

Cada recomendação contém: problema, itens/evidências, impacto observado, hipótese quando houver, ação candidata, papel decisor sugerido, informação a confirmar e critério para verificar o resultado. Estimativa de benefício não é inventada. Cenário de transferência mostra apenas o efeito aritmético da carga removida/adicionada, sob hipótese explícita, sem prometer produtividade ou prazo.

## 4. Acompanhamento das ações

Primeira versão: abrir item no ADO, copiar recomendação e exportar lista de decisões em JSON/Markdown. O HTML pode manter rascunho de decisões na memória da página e exportá-lo; fechar sem exportar não preserva alterações. Não prometer sincronização de um HTML offline nem usar estado local de navegador como registro oficial.

O registro exportado contém run ID, finding ID, ação, responsável informado, prazo informado, estado (proposta, aceita, em andamento, concluída, descartada), justificativa e evidência de conclusão. O núcleo importa o arquivo explicitamente em uma nova execução, preservando trilha e origem humana. Não editar snapshots antigos. IDs de achados permanecem estáveis por regra + entidade; reaparecimento em outra execução não é automaticamente uma nova ação.

Ação recomendada não é ação executada. Criar tarefas, alterar responsáveis ou postar comentários no ADO continua fora do escopo de leitura. Uma futura escrita também usará exclusivamente ferramenta do MCP oficial e exigirá contrato próprio com prévia da mudança, autorização, checagem de revisão do item e idempotência; este pedido de estudo não ativa escrita.

## 5. Conteúdo por release

| v0.1 — obrigatório | v0.2 — com histórico | Posterior |
|---|---|---|
| Objetivo informado, escopo atual e qualidade | Burnup/burndown observados | Forecast probabilístico calibrado |
| Capacidade/carga conhecida, gap e unidades | Baseline de horas e variação por causa | Escrita no ADO com fluxo próprio |
| Impedimentos explícitos e dependências | Duração de bloqueios e aging histórico | Colaboração online em decisões |
| Candidatos de ação com evidência | CFD, cycle time e tendências | Publicação do relatório em serviço |
| Filtros, detalhamento, exportação de decisões | Say/do e carry-over por coorte | |

Não priorizar no topo: ranking de pessoas, velocity comparada entre equipes, percentual de produtividade, score opaco de saúde, previsão baseada apenas na linha ideal do burndown ou precisão de estimativa sem registro confiável.

## 6. Aceite do relatório

- Leitor identifica até três decisões prioritárias sem percorrer todas as tasks.
- Números e referências coincidem com JSON/Markdown em todos os hosts.
- Gráficos têm tabela equivalente, legenda textual e não dependem só de cores; uso por teclado e impressão legível são verificados.
- Filtros por equipe, atividade, estado e responsável mostram a seleção ativa e não misturam total filtrado com total da sprint.
- Sem baseline, histórico, estimativa ou impedimento mapeado, o bloco explica a limitação; não mostra zero ou gráfico fictício.
- Exportação/importação de ações preserva identidade e autoria humana sem enviar mensagens ao ADO.
- Títulos/descrições maliciosos não executam HTML/JavaScript; links e arquivos importados são validados.
- Piloto com gestor e membro do time identifica decisões úteis e falsos positivos; correções viram regras/testes, não frases escondidas no prompt.
