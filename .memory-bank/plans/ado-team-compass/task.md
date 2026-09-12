# Checklist de implementação do ado-team-compass — v1.3

IPD de origem: [plan.md](plan.md) · Decisões: [architecture.md](architecture.md) · Data: 12/09/2026.

## Resumo executivo

Objetivo: construir e distribuir visibilidade de entrega ADO com evidência auditável e adaptação por equipe. Complexidade L no núcleo / XL no escopo remoto. São 28 tarefas em cinco releases; 19 entregam a v0.1. T26/T27 aparecem antes de T14 para preservar os IDs anteriores e respeitar dependências. Todas estão pendentes: este documento não registra implementação executada.

Cada tarefa deve produzir uma entrega revisável. Os IDs M remetem ao mapa de alterações do plano, V aos cenários de teste e DOD aos critérios de pronto. Testes e documentação acompanham a responsabilidade implementada, além das validações transversais explicitamente separadas.

## Guardrails herdados

- Cálculo puro com entradas, versões e relógio explícitos; nenhuma matemática de gestão delegada ao LLM.
- Ausência não é zero; original não é restante; pontos não são horas; reserva de time não é disponibilidade pessoal.
- Dados incompletos devem chegar identificados ao relatório; nenhuma classificação de ociosidade real ou produtividade individual.
- Todo acesso ADO exclusivamente pelo MCP oficial Microsoft, sem REST/OData/SDK/CLI direto; operações somente de leitura; fontes de texto são dados, não instruções.
- Credenciais e dados reais não entram em fixtures públicas; estado não fica no diretório instalado do plugin.
- Artefatos de execução são imutáveis, e testes de instalação precisam usar o pacote produzido.

## Sequência de tarefas

### T01 — Criar pacote e infraestrutura de qualidade

- Status: CONCLUIDA (12/09/2026)
- Release/Fase: v0.1 / F0
- Objetivo: estabelecer projeto instalável e verificação automatizada antes das métricas.
- Base no IPD: 2.2, 3.1, 4.3 e 4.4.
- Áreas impactadas: M01, M02, M14, M15, M16.
- Dependências: nenhuma.
- Entregável esperado: pacote Python, lock de dependências, CLI mínima, CI e fixture sintética mínima.
- Check de conclusão:
  - [x] Pacote construído instala em ambiente isolado e informa sua versão (`uv build` + wheel instalada em venv isolada: `ado-team-compass version`).
  - [x] Testes, estilo e checagem de tipos executam no CI sem credenciais (`.github/workflows/ci.yml`: ruff, mypy, pytest `-m "not integration"`).
  - [x] Git ignora somente dados de execução e overrides locais; exemplo compartilhável continua versionável (`.gitignore`, `examples/config/`).
- Riscos ou atenções: não confundir ausência de infraestrutura prévia com dispensa de testes.

### T02 — Implementar schemas e resolução de configuração

- Status: CONCLUIDA (12/09/2026)
- Release/Fase: v0.1 / F0
- Objetivo: estabilizar o contrato entre fonte, cálculo e narrativa.
- Base no IPD: 4.1.2, 4.1.3; arquitetura D03 e D05.
- Áreas impactadas: M03, M04, M14, M16.
- Dependências: T01.
- Entregável esperado: modelos tipados, schemas exportados, perfis iniciais e configuração efetiva sanitizada.
- Check de conclusão:
  - [x] Ausente, zero e não aplicável são representáveis separadamente (`Quantity.value` nulo, `MetricStatus`, `Coverage` com denominador desconhecido).
  - [x] Precedência de configuração é determinística e tem teste (`product_default → profile → team → local → run`, com proveniência por chave).
  - [x] Major desconhecida e campos inválidos geram erro acionável (`E_CFG_SCHEMA_MAJOR_DESCONHECIDA` → saída 6; `E_CFG_INVALIDA` com caminho da violação).
  - [x] Fixtures de todos os contratos passam pela validação (`tests/fixtures/contracts/`, ida e volta preservada).
- Riscos ou atenções: nenhuma regra executável arbitrária no YAML; preservação de unidades.

### T03 — Implementar cliente do MCP oficial e sessão

- Status: CONCLUIDA (12/09/2026) — transporte remoto oficial como padrão; handshake real ainda não executado contra organização
- Release/Fase: v0.1 / F1
- Objetivo: conectar ao MCP oficial e coletar somente por ferramentas/ações de leitura autorizadas.
- Base no IPD: 4.1.1, 4.4 e 5.
- Áreas impactadas: M02, M05, M06, M14, M16.
- Dependências: T02.
- Entregável esperado: cliente MCP, sessão segura, descoberta de catálogo e schemas, allowlist por ferramenta/ação e transporte com controle de erros.
- Check de conclusão:
  - [x] Servidor oficial, organização e sessão são verificáveis sem expor credenciais (`doctor` reporta canal, versão, hash de catálogo e erros sanitizados).
  - [x] Operações permitidas de leitura são explícitas por ferramenta e ação, inclusive em ferramentas mistas (allowlist por operação + recusa de verbo de escrita por segmento de nome).
  - [x] V11 cobre sessão expirada, acesso negado, retentativa limitada e timeout; V33 prova ausência de fallback direto e bloqueio de escrita (varredura estática do código de produto + testes de catálogo/offline).
  - [x] Logs de exceção e diagnóstico passam por verificação de segredo (`sanitize_detail` no registro de chamadas e no diagnóstico).
- Riscos ou atenções: não implementar autenticação ADO paralela; usar somente modos suportados pelo MCP oficial conectado.

### T04 — Entregar setup por perfil de equipe

- Status: CONCLUIDA (12/09/2026) — descoberta validada por fixture; cobertura real por confirmar no primeiro handshake
- Release/Fase: v0.1 / F1
- Objetivo: configurar várias equipes sem modificar código.
- Base no IPD: 4.1.2 e 7.2.
- Áreas impactadas: M04, M06, M14, M16.
- Dependências: T03.
- Entregável esperado: descoberta via MCP por ID de organização/projeto/equipe, áreas, iterações, campos e estados quando expostos; perfis e limites aplicados.
- Check de conclusão:
  - [x] Perfis sprint com horas, sprint sem horas e fluxo contínuo são configuráveis (`build_config_document(profiles=...)`; padrão conservador sem horas).
  - [x] Equipes com nomes iguais são desambiguadas por projeto/ID (V13: `plataforma-core` e `dados-core`).
  - [x] Inclusão de áreas descendentes é respeitada (vem de `teamFieldValues` do MCP; desconhecida não é assumida).
  - [x] Mapeamento desconhecido desabilita a métrica dependente com motivo; V10 e V13 cobertos (limitações por equipe + `assess_metric`).
- Riscos ou atenções: descoberta técnica não prova política de negócio nem compromisso da sprint.

### T05 — Coletar e normalizar a situação atual

- Status: CONCLUIDA (12/09/2026) — validada com fixture sintética; formatos reais de resposta a confirmar no primeiro handshake
- Release/Fase: v0.1 / F1
- Objetivo: produzir fatos completos dentro do escopo selecionado.
- Base no IPD: 4.1.3, 4.1.4 e 4.2.
- Áreas impactadas: M06, M07, M14, M16.
- Dependências: T04.
- Entregável esperado: itens, pessoas, capacidade, calendários e relações normalizados com origem.
- Check de conclusão:
  - [x] Paginação e leitura em lote preservam contagens esperadas (lotes de 200; lote incompleto vira cobertura parcial declarada).
  - [x] IDs duplicados não geram fatos duplicados; V06 e V09 cobertos (dedupe por organização + ID; hierarquia por `System.Parent`).
  - [x] Bugs, estados customizados e renomeações são tratados conforme perfil (categoria só por mapeamento local; identidade por ID).
  - [x] Fonte incompleta carrega motivo e cobertura até a saída; V11 e V13 cobertos (`partial_sources` + `reasons` no FactSet).
- Riscos ou atenções: coleta de fontes diferentes não equivale a snapshot transacional único.

### T06 — Adicionar cache, evidência e recuperação de falhas

- Status: CONCLUIDA (12/09/2026)
- Release/Fase: v0.1 / F1
- Objetivo: permitir auditoria e repetição sem misturar identidades ou coletas.
- Base no IPD: 4.1.3, 5 e 7.1.
- Áreas impactadas: M06, M07, M10, M14, M16.
- Dependências: T05.
- Entregável esperado: cache isolado, identificação de fonte e estado de coleta parcial.
- Check de conclusão:
  - [x] Cache separa organização, identidade, escopo, período e versão relevante (`CacheKey` com teste por dimensão).
  - [x] Falha intermediária não produz execução marcada como completa (manifesto escrito por último; `abandon` deixa a execução não carregável e preserva a anterior).
  - [x] Evidência minimizada permite explicar um total sem credencial ou descrição integral (excerto de título de 80 caracteres, sem descrição).
  - [x] Alteração de identidade não reutiliza silenciosamente cache de outro usuário (identidade só como hash opaco na chave).
- Riscos ou atenções: sanitização de evidência deve manter os fatos necessários à reprodução.

### T07 — Implementar qualidade por métrica

- Status: CONCLUIDA (12/09/2026)
- Release/Fase: v0.1 / F2
- Objetivo: determinar quais resultados são utilizáveis para cada perfil.
- Base no IPD: 4.1.2–4.1.4.
- Áreas impactadas: M04, M08, M14, M16.
- Dependências: T02, T05.
- Entregável esperado: requisitos de cada métrica, status, cobertura e motivos.
- Check de conclusão:
  - [x] V02 distingue carga conhecida de itens sem restante (`metrics/quality.py`, status `partial` com contadores).
  - [x] V10 não penaliza equipe sem horas por campos não aplicáveis (`not_applicable` com motivo, sem cobertura e sem achado).
  - [x] Denominador desconhecido não vira cobertura total (`Coverage.ratio` nulo quando `eligible` é desconhecido).
  - [x] Nenhum score agregado é apresentado como percentual de confiança (teste verifica ausência dessa API).
- Riscos ou atenções: cobertura de itens não é cobertura do esforço desconhecido.

### T08 — Implementar calendário e capacidade restante

- Status: CONCLUIDA (12/09/2026)
- Release/Fase: v0.1 / F2
- Objetivo: calcular disponibilidade reservada na janela correta.
- Base no IPD: 4.1.4.
- Áreas impactadas: M04, M09, M14, M16.
- Dependências: T02; integração final depende de T05.
- Entregável esperado: funções puras de janela, dias elegíveis, folgas e capacidade por atividade.
- Check de conclusão:
  - [x] V01 valida união de feriados/folgas sem desconto duplicado (capacidade 24, não 18).
  - [x] V12 valida timezone, limites de sprint e política do dia atual (fim inclusivo normalizado; sem rateio intradiário).
  - [x] V08 impede conversão implícita entre dias e horas (reservas em unidades distintas não agregam).
  - [x] Folgas parciais e capacidade nula têm comportamentos documentados (maior fração vence; per_day nulo permanece ausente).
- Riscos ou atenções: fixtures podem permitir desenvolvimento paralelo à coleta; contrato não muda unilateralmente.

### T09 — Implementar carga e classificações locais

- Status: CONCLUIDA (12/09/2026)
- Release/Fase: v0.1 / F2
- Objetivo: comparar carga conhecida e capacidade restante de cada equipe.
- Base no IPD: 4.1.4.
- Áreas impactadas: M09, M14, M16.
- Dependências: T07, T08.
- Entregável esperado: carga por pessoa/atividade, carga sem responsável e classes com limites explícitos.
- Check de conclusão:
  - [x] V02, V03 e V07 preservam ausências e impedem divisão inválida (`CARGA_SEM_CAPACIDADE`; zero/zero sem percentual).
  - [x] V09 evita soma de pai e filho; itens excluídos ficam explicados (nível único + achados por item).
  - [x] Limiares 0,60, 0,90 e 1,10 possuem testes de fronteira (8 casos parametrizados).
  - [x] Dados parciais não geram falsa classificação de baixa carga (`DADOS_INSUFICIENTES` com limite inferior).
- Riscos ou atenções: todo percentual deve usar mesma janela e unidade do numerador.

### T10 — Implementar consolidação entre equipes

- Status: CONCLUIDA (12/09/2026) — cálculo puro; integração com coleta real depende de T05/T06
- Release/Fase: v0.1 / F2
- Objetivo: expor reservas sobrepostas e carga observada sem fabricar disponibilidade.
- Base no IPD: 4.1.4; arquitetura D04.
- Áreas impactadas: M07, M09, M14, M16.
- Dependências: T09, T06.
- Entregável esperado: visão por pessoa na organização selecionada, com cobertura de equipes e janela comum.
- Check de conclusão:
  - [x] V04 aponta reserva acima da disponibilidade pessoal (60 reservados contra 30 informados).
  - [x] V05 deixa utilização global nula sem disponibilidade validada (sem inferir jornada padrão).
  - [x] V06 deduplica itens e preserva múltiplos pertencimentos (`deduplicate_items` une `team_memberships`).
  - [x] Projetos/sprints diferentes e acesso parcial têm cobertura explícita; V08 coberto (união de dias elegíveis; unidades incompatíveis não agregam).
- Riscos ou atenções: não consolidar pessoas de organizações diferentes por nome ou e-mail.

### T11 — Persistir execução e gerar relatório determinístico

- Status: PENDENTE
- Release/Fase: v0.1 / F3
- Objetivo: entregar resultado útil e auditável sem depender do assistente.
- Base no IPD: 4.1.1, 4.1.3 e 4.2.
- Áreas impactadas: M02, M10, M11, M14, M16.
- Dependências: T06, T10.
- Entregável esperado: manifesto, fatos, métricas, resumo limitado e Markdown; leitura de evidências e replay.
- Check de conclusão:
  - [ ] V14 confirma igualdade de métricas no replay.
  - [ ] Cada número do relatório aponta para métrica/evidência da execução.
  - [ ] Resumo excedente é reduzido deterministicamente com indicador de truncamento.
  - [ ] Escrita interrompida não substitui execução válida por saída incompleta.
- Riscos ou atenções: hashes não são assinatura de autenticidade; fatos completos não podem ser truncados.

### T12 — Delimitar e validar interpretação do LLM

- Status: PENDENTE
- Release/Fase: v0.1 / F3
- Objetivo: acrescentar interpretação sem inventar números ou causalidade.
- Base no IPD: 4.1.3, 4.1.4 e 5.
- Áreas impactadas: M03, M11, M14, M16.
- Dependências: T11.
- Entregável esperado: contrato de narrativa, validação de referências e conjunto de avaliações.
- Check de conclusão:
  - [ ] Fatos, hipóteses e ações são campos separados.
  - [ ] V15 e V16 rejeitam instruções em dados e referências inexistentes.
  - [ ] Pedidos de ranking individual não geram classificação de produtividade.
  - [ ] Falha de narrativa preserva relatório determinístico.
- Riscos ou atenções: validação estrutural não prova verdade de toda prosa; incluir avaliação semântica por cenários e inspeção no piloto.

### T13 — Criar integração Claude Code

- Status: PENDENTE
- Release/Fase: v0.1 / F3
- Objetivo: executar os casos principais por linguagem natural e entradas estáveis.
- Base no IPD: 4.1.1, 4.3; arquitetura D01 e D07.
- Áreas impactadas: M02, M12, M13, M21, M14, M16.
- Dependências: T12.
- Entregável esperado: manifesto Claude e fonte compartilhada de instruções de setup, diagnóstico, situação atual, daily resumido e alocação, consumida pelos demais bundles.
- Check de conclusão:
  - [ ] Skills usam motor instalado e não dependem da pasta de desenvolvimento.
  - [ ] Argumentos e caminhos com espaços são tratados sem interpolação insegura.
  - [ ] Invocações naturais em português selecionam o comportamento esperado.
  - [ ] Coleta exige MCP oficial conectado; somente demo, replay e renderização de dados locais funcionam sem MCP.
- Riscos ou atenções: não duplicar comandos e skills desnecessariamente; não hardcodar caminhos do autor.

### T26 — Criar bundle Antigravity

- Status: PENDENTE
- Release/Fase: v0.1 / F3
- Objetivo: executar o mesmo produto no Antigravity IDE sem instruções exclusivas de Claude.
- Base no IPD: 4.1.7; arquitetura D09.
- Áreas impactadas: M21, M13, M14, M16.
- Dependências: T13.
- Entregável esperado: pacote com manifesto próprio, skills geradas da fonte comum e guia de instalação por versão de IDE.
- Check de conclusão:
  - [ ] Instalação em perfil limpo descobre skills e encontra o motor fora da árvore de desenvolvimento.
  - [ ] V25 reproduz métricas e limites da fixture usada no Claude; V26 isola atualização e remoção.
  - [ ] Nenhuma variável CLAUDE_PLUGIN_ROOT ou sintaxe de ferramenta Claude vaza para o bundle.
  - [ ] Caminhos com espaços, erros de autenticação e dados parciais são avaliados no host real.
- Riscos ou atenções: testar o IDE explicitamente; compatibilidade com CLI/SDK não é inferida.

### T27 — Criar bundle Codex/OpenAI

- Status: PENDENTE
- Release/Fase: v0.1 / F3
- Objetivo: permitir uso com modelos GPT no ambiente Codex sem duplicar lógica.
- Base no IPD: 4.1.7; arquitetura D09.
- Áreas impactadas: M22, M13, M14, M16.
- Dependências: T13.
- Entregável esperado: manifesto Codex, skills da fonte comum, instalação em host local suportado e guia próprio.
- Check de conclusão:
  - [ ] Bundle inclui manifesto e assets em formato válido para a versão testada.
  - [ ] V25 e V26 passam no Codex CLI e na superfície desktop suportada, com versão registrada.
  - [ ] Coleta exige MCP oficial; cálculo/replay local não exige rede nem chave de API OpenAI adicional.
  - [ ] Diagnóstico não promete compatibilidade com GPT personalizado ou extensão IDE a partir do teste local.
- Riscos ou atenções: modelo é configuração do host; não fixar identificador GPT no motor.

### T22 — Entregar HTML de sprint e apoio à decisão

- Status: PENDENTE
- Release/Fase: v0.1 / F3; enriquecimento histórico por T21 na v0.2.
- Objetivo: apoiar acompanhamento de entrega, planejamento de horas, desvios, gargalos, impedimentos e decisões em um relatório navegável.
- Base no IPD: 4.1.6, 13 e contrato docs/sprint-report.md.
- Áreas impactadas: M02, M03, M11, M12, M21, M22, M24, M14, M16.
- Dependências: T12, T26, T27.
- Entregável esperado: HTML offline, candidatos de ação com evidência e registro humano exportável/importável, disponível pelos três bundles locais.
- Check de conclusão:
  - [ ] DOD13 atendido: objetivo informado, entrega atual, capacidade/carga, gap, impedimentos explícitos e até três decisões prioritárias.
  - [ ] V15 impede execução de conteúdo do ADO; tabelas equivalentes, teclado, impressão e filtros são verificados.
  - [ ] V29–V31 distinguem fatos, estimativas incompletas, histórico ausente e hipóteses; não desenhar passado fictício.
  - [ ] V32 preserva IDs/autoria na exportação/importação, sem sincronização implícita nem escrita no ADO.
  - [ ] Métricas coincidem com JSON/Markdown; links de detalhes rastreiam execução e limites.
- Riscos ou atenções: baseline, burnup/burndown histórico, duration de bloqueios e variação de esforço exigem T17–T21; v0.1 informa indisponibilidade. A recomendação não executa a mudança.

### T14 — Executar validação transversal da v0.1

- Status: PENDENTE
- Release/Fase: v0.1 / F4
- Objetivo: provar integridade, reprodutibilidade e portabilidade do candidato.
- Base no IPD: 3.1, 5 e 6.
- Áreas impactadas: M10, M14, M15, M16.
- Dependências: T13, T26, T27, T22.
- Entregável esperado: relatório de testes, retenção/purga validada e medição offline.
- Check de conclusão:
  - [ ] V01–V16, V25–V26, V29–V32 aplicáveis à v0.1 e V33 passam nos hosts aplicáveis; evidências numéricas têm expectativa revisada independentemente.
  - [ ] Verificação de segredos cobre falhas e artefatos.
  - [ ] Replay, compatibilidade de schema e retenção de 30 dias estão verificados.
  - [ ] Benchmark de referência é registrado; desvios da meta têm causa e decisão.
- Riscos ou atenções: golden file aprovado não substitui teste de fórmula nem contrato externo.

### T15 — Empacotar release candidata e marketplace

- Status: PENDENTE
- Release/Fase: v0.1 / F4
- Objetivo: tornar a instalação reproduzível fora do ambiente de desenvolvimento.
- Base no IPD: 4.3, 4.4 e 9.
- Áreas impactadas: M01, M12, M13, M21, M22, M14, M15, M16.
- Dependências: T14.
- Entregável esperado: wheel, bundle da integração com dependências fixadas, catálogo, checksums e guia de instalação/rollback.
- Check de conclusão:
  - [ ] Motor instala em Windows, macOS e Linux; cada bundle instala nas combinações host/SO declaradas na matriz, sem editar código.
  - [ ] V21 valida atualização, compatibilidade e rollback preservando dados.
  - [ ] Instalação assistida/offline e proxy têm procedimentos explícitos.
  - [ ] Demo não requer token nem acesso ao ADO.
- Riscos ou atenções: usar o próprio artefato produzido; não provar instalação a partir da árvore de fontes.

### T16 — Validar piloto e preparar liberação da v0.1

- Status: PENDENTE
- Release/Fase: v0.1 / F4
- Objetivo: validar utilidade e correção em práticas reais diferentes.
- Base no IPD: 1.2, 3.1 e 9.
- Áreas impactadas: M14, M16; correções retornam à tarefa dona do módulo.
- Dependências: T15; acesso e responsáveis por três equipes piloto.
- Entregável esperado: registro sanitizado de reconciliação, compatibilidade e decisão de liberação.
- Check de conclusão:
  - [ ] Três perfis funcionam com configuração, sem ramificação por cliente.
  - [ ] Totais completos e amostra de itens são reconciliados; divergências são explicadas ou corrigidas.
  - [ ] Usuário novo instala demo em até 15 minutos com pré-requisitos presentes, ou a meta é revisada com evidência.
  - [ ] DOD01–DOD10, DOD13, DOD16 e DOD18 atendidos; destino e licença definidos antes de qualquer publicação pública.
- Riscos ou atenções: indisponibilidade do piloto não autoriza afirmar validação real; publicação externa não é ação implícita desta tarefa de documentação.

### T17 — Adicionar coleta histórica consistente

- Status: PENDENTE
- Release/Fase: v0.2 / F5
- Objetivo: obter fatos históricos com corte e granularidade explícitos.
- Base no IPD: 4.1.5 e 4.4.
- Áreas impactadas: M02, M03, M06, M07, M14, M16.
- Dependências: T16.
- Entregável esperado: coleta de revisões/consultas históricas suportadas pelo MCP oficial e snapshots locais com proveniência MCP.
- Check de conclusão:
  - [ ] Catálogo MCP e cobertura histórica são verificados; fonte/ferramenta ausente desabilita a métrica, sem bypass (V33).
  - [ ] Paginação/filtros verificam cobertura de itens movidos de área/iteração; sem cobertura comprovada, resultado é parcial.
  - [ ] V17 preserva o corte na consulta e na hidratação.
  - [ ] Itens excluídos, lacunas e divergência entre fontes são limitações explícitas.
- Riscos ou atenções: snapshot local diário não substitui evento intradiário; não reconstruir passado anterior à primeira coleta sem revisão completa no MCP.

### T18 — Implementar compromisso e mudança de escopo

- Status: PENDENTE
- Release/Fase: v0.2 / F5
- Objetivo: medir previsibilidade sem contaminar a baseline com dados atuais.
- Base no IPD: 4.1.5.
- Áreas impactadas: M17, M14, M16.
- Dependências: T17.
- Entregável esperado: baseline, say/do, entradas/saídas, carry-over, pontos/estimativas congelados e variação de esforço separada de mudança de escopo e capacidade.
- Check de conclusão:
  - [ ] V17, V19 e V30 validam reestimativa, entrada/saída, coorte de horas e denominador zero.
  - [ ] Baseline técnica é distinguida de compromisso confirmado.
  - [ ] Itens adicionados não aumentam cumprimento da baseline original.
  - [ ] Percentuais têm coorte, numerador, denominador e corte disponíveis.
- Riscos ou atenções: carry-over da baseline não equivale a transferência comprovada para a próxima sprint.

### T19 — Implementar regras de planejamento por perfil

- Status: PENDENTE
- Release/Fase: v0.2 / F5
- Objetivo: apontar inconsistências de acordo com políticas explicitadas.
- Base no IPD: 4.1.5.
- Áreas impactadas: M02, M04, M11, M18, M14, M16.
- Dependências: T17; regras atuais reutilizam T05.
- Entregável esperado: catálogo de regras, severidades, exceções e relatório com IDs.
- Check de conclusão:
  - [ ] Regras iniciais têm casos positivos, negativos e ausências de campo.
  - [ ] V20 confirma silêncio para políticas desativadas.
  - [ ] Achado exibe regra/versionamento, evidência e condição violada.
  - [ ] Exceção tem justificativa e não apaga o dado de origem.
- Riscos ou atenções: não considerar requisito universal a existência de tasks, estimativa ou área igual à do pai.

### T20 — Implementar métricas de fluxo e coortes

- Status: PENDENTE
- Release/Fase: v0.2 / F5
- Objetivo: gerar séries históricas interpretáveis e consistentes.
- Base no IPD: 4.1.5.
- Áreas impactadas: M17, M14, M16.
- Dependências: T17.
- Entregável esperado: throughput, lead/cycle time, aging, reaberturas, duração de impedimentos quando há eventos, filas por etapa e percentis.
- Check de conclusão:
  - [ ] V18 prova a política de primeira conclusão e reabertura; V31 impede inferir duração de bloqueio pela última alteração genérica.
  - [ ] Percentil informa método, unidade, amostra e janela; amostra vazia é nula.
  - [ ] Períodos sem entrega permanecem na série.
  - [ ] Mudança de política/processo é identificada e não produz comparação silenciosa.
- Riscos ou atenções: correlação de WIP e cycle time não demonstra causa; não comparar pontos entre times.

### T21 — Integrar e validar a release histórica

- Status: PENDENTE
- Release/Fase: v0.2 / F5
- Objetivo: entregar histórico e planejamento com evidência equivalente à v0.1.
- Base no IPD: 3.2, 4.1.5 e 9.
- Áreas impactadas: M11, M12, M21, M22, M24, M14, M16.
- Dependências: T18, T19, T20.
- Entregável esperado: relatórios e skills de histórico/planejamento nos três bundles, gerados da fonte comum, e registro de validação.
- Check de conclusão:
  - [ ] V17–V20 e V30–V31 passam; HTML recebe burnup/burndown, baseline de esforço e tendências quando disponíveis; DOD11–DOD12 são atendidos.
  - [ ] Série de seis sprints ou janela de fluxo equivalente é reconciliada em equipe com histórico disponível.
  - [ ] Regressões da v0.1 passam sem exigir histórico.
  - [ ] Dados insuficientes limitam a saída de modo acionável.
- Riscos ou atenções: evolução de release exige reuso do processo de pacote e atualização de versão.

### T23 — Implementar executor agendável via MCP oficial

- Status: PENDENTE
- Release/Fase: v0.3 / F6
- Objetivo: executar coleta e relatório sem sessão interativa do assistente.
- Base no IPD: 4.1.6 e 4.4.
- Áreas impactadas: M02, M04, M05, M10, M19, M14, M16.
- Dependências: T21; integração visual final depende de T22.
- Entregável esperado: cliente MCP não interativo oficialmente suportado, chave de idempotência, lock e template de pipeline.
- Check de conclusão:
  - [ ] Modo não interativo do MCP oficial tem leitura validada no ambiente; se não suportado, coleta agendada é indisponível sem fallback direto (V33).
  - [ ] V22 evita duplicação e preserva sucesso anterior quando nova execução falha.
  - [ ] Artefato e logs ficam em destino privado configurado.
  - [ ] Falta de credencial/configuração encerra com código estável, sem esperar diálogo.
- Riscos ou atenções: implementação do template não ativa agenda nem publica relatório por conta própria.

### T24 — Validar operação, retenção e avisos

- Status: PENDENTE
- Release/Fase: v0.3 / F6
- Objetivo: tornar a execução repetida previsível e recuperável.
- Base no IPD: 3.2, 4.1.6 e 9.
- Áreas impactadas: M19, M14, M16.
- Dependências: T22, T23.
- Entregável esperado: runbook de operação, aviso local opcional e evidência de execução agendada.
- Check de conclusão:
  - [ ] DOD14 atendido e V22 exercitado em integração.
  - [ ] Hook consulta apenas metadados locais e não dispara autenticação/rede.
  - [ ] Runbook cobre expiração de credencial, retry, retenção, rollback e artefato parcial.
  - [ ] Canal de notificação só é ativado com configuração e autorização, sem mensagens repetidas quando nada mudou.
- Riscos ou atenções: não confundir cronologia da agenda com calendário de trabalho ou fuso do time.

### T25 — Entregar forecast experimental com backtesting

- Status: PENDENTE
- Release/Fase: v0.4 / F7
- Objetivo: projetar conclusão sob premissas verificáveis e medir a qualidade da projeção.
- Base no IPD: 4.1.6 e 6.
- Áreas impactadas: M02, M03, M11, M20, M14, M16.
- Dependências: T17, T20, T21; não exige automação da v0.3.
- Entregável esperado: distribuição de datas, p50/p85, premissas, semente, amostra e relatório retrospectivo.
- Check de conclusão:
  - [ ] V23 recusa amostra insuficiente e preserva períodos de throughput zero.
  - [ ] V24 impede vazamento de futuro e reproduz o resultado por semente.
  - [ ] Escopo restante, equipe, comparabilidade e cenários estão declarados.
  - [ ] DOD15 atendido; cobertura empírica é publicada e resultado permanece experimental se não calibrado.
- Riscos ou atenções: percentil é cenário probabilístico condicionado ao modelo, não garantia de prazo.

### T28 — Integrar GPT personalizado via API autenticada

- Status: PENDENTE
- Release/Fase: v0.3.1 / F6b
- Objetivo: consultar no ChatGPT os relatórios do motor por GPT Actions, sem executar scripts locais.
- Base no IPD: 4.1.7; arquitetura D09; matriz de compatibilidade.
- Áreas impactadas: M23, M14, M16; extra de dependências em M01.
- Dependências: T24; domínio HTTPS, provedor OAuth e ambiente de teste com Actions habilitado.
- Entregável esperado: gateway dedicado por organização, contrato OpenAPI, instruções do GPT, template de implantação e testes de autorização.
- Check de conclusão:
  - [ ] GPT lista apenas equipes autorizadas e consulta relatório/evidência por referências válidas.
  - [ ] V27 bloqueia token inválido, equipe/run não autorizado e usuário revogado, inclusive em links de artefato.
  - [ ] V28 preserva timestamp, status parcial, ausência e limites de resposta; nenhum dado é calculado pelo GPT.
  - [ ] Coletor usa somente o MCP oficial; nenhuma credencial ADO direta fica no coletor, instruções, OpenAPI ou respostas (V33).
  - [ ] DOD17 é demonstrado com usuário permitido e negado no ambiente real; falhas de deploy e rollback são documentadas.
- Riscos ou atenções: não ativar exposição remota ou publicar GPT automaticamente; compatibilidade depende de implantação e permissões do workspace. SDK/OpenAI API para chamar modelos é escopo separado.

## Cobertura do DoD

| Critério | Tarefas responsáveis |
|---|---|
| DOD01 — instalação e demo | T01, T15, T16 |
| DOD02 — setup por perfil | T02, T04 |
| DOD03 — leitura e falhas | T03, T05, T06 |
| DOD04 — ausências/unidades | T02, T07, T09 |
| DOD05 — calendário e carga | T08, T09, T10 |
| DOD06 — auditoria | T06, T11 |
| DOD07 — narrativa | T12, T13, T16 |
| DOD08 — qualidade | T01, T14, T16 |
| DOD09 — segredos/retenção | T03, T06, T14 |
| DOD10 — piloto/distribuição | T15, T16 |
| DOD11 — histórico | T17, T18, T20, T21 |
| DOD12 — planejamento | T19, T21 |
| DOD13 — HTML | T22 |
| DOD14 — operação | T23, T24 |
| DOD15 — forecast | T25 |
| DOD16 — paridade de hosts | T13, T26, T27, T14, T15, T16 |
| DOD17 — GPT remoto | T28 |
| DOD18 — MCP exclusivo | T03, T14, T17, T23, T28 |

## Lacunas e pré-condições operacionais

Não há código existente nem credenciais verificadas. T01 inicia sem depender dessas credenciais. Acesso real e equipes piloto são necessários para concluir T16; histórico real é necessário para T21; conexão MCP oficial não interativa suportada e destino privado são necessários para a validação operacional de T23/T24. Repositório privado definido: LuisCarlosLopes/ado-team-compass. Licença continua necessária antes de publicação pública; domínio HTTPS/provedor OAuth e conta com Actions são pré-condições operacionais de T28. Nenhuma dessas validações foi executada durante a criação deste plano.

## Matriz de rastreabilidade

| Tarefa | Base no IPD | Áreas | Testes e DoD principais |
|---|---|---|---|
| T01 | 2.2, 3.1, 4.4 | M01, M02, M14, M15, M16 | DOD01, DOD08 |
| T02 | 4.1.2–4.1.3 | M03, M04, M14, M16 | DOD02, DOD04 |
| T03 | 4.1.1, 4.4, 5 | M02, M05, M06, M14, M16 | V11, V33; DOD03, DOD09, DOD18 |
| T04 | 4.1.2 | M04, M06, M14, M16 | V10, V13; DOD02 |
| T05 | 4.1.3–4.1.4 | M06, M07, M14, M16 | V06, V09, V11, V13; DOD03 |
| T06 | 4.1.3, 5 | M06, M07, M10, M14, M16 | V11; DOD03, DOD06, DOD09 |
| T07 | 4.1.2–4.1.4 | M04, M08, M14, M16 | V02, V10; DOD04 |
| T08 | 4.1.4 | M04, M09, M14, M16 | V01, V08, V12; DOD05 |
| T09 | 4.1.4 | M09, M14, M16 | V02, V03, V07, V08, V09; DOD04, DOD05 |
| T10 | 4.1.4 | M07, M09, M14, M16 | V04, V05, V06, V08; DOD05 |
| T11 | 4.1.1, 4.1.3 | M02, M10, M11, M14, M16 | V14; DOD06 |
| T12 | 4.1.3, 5 | M03, M11, M14, M16 | V15, V16; DOD07 |
| T13 | 4.1.1, 4.3, 4.1.7 | M02, M12, M13, M21, M14, M16 | V16, V25; DOD07, DOD16 |
| T14 | 3.1, 5, 6, 13 | M10, M14, M15, M16 | V01–V16, V25–V26, V29–V33; DOD08, DOD09, DOD13, DOD16, DOD18 |
| T15 | 4.3, 4.4, 9 | M01, M12, M13, M21, M22, M14, M15, M16 | V21, V26; DOD01, DOD10, DOD16 |
| T16 | 1.2, 3.1, 9 | M14, M16 | V10, V21; DOD01–DOD10 |
| T17 | 4.1.5, 4.4 | M02, M03, M06, M07, M14, M16 | V17, V33; DOD11, DOD18 |
| T18 | 4.1.5, 13 | M17, M14, M16 | V17, V19, V30; DOD11 |
| T19 | 4.1.5 | M02, M04, M11, M18, M14, M16 | V20; DOD12 |
| T20 | 4.1.5, 13 | M17, M14, M16 | V18, V31; DOD11 |
| T21 | 3.2, 4.1.5, 9, 13 | M11, M12, M21, M22, M24, M14, M16 | V17–V20, V30–V31; DOD11, DOD12 |
| T22 | 4.1.6, 13 | M02, M03, M11, M12, M21, M22, M24, M14, M16 | V15, V29–V32; DOD13 |
| T23 | 4.1.6, 4.4 | M02, M04, M05, M10, M19, M14, M16 | V22, V33; DOD14, DOD18 |
| T24 | 3.2, 4.1.6, 9 | M19, M14, M16 | V22, V33; DOD14, DOD18 |
| T25 | 4.1.6, 6 | M02, M03, M11, M20, M14, M16 | V23, V24; DOD15 |
| T26 | 4.1.7 | M21, M13, M14, M16 | V25, V26; DOD16 |
| T27 | 4.1.7 | M22, M13, M14, M16 | V25, V26; DOD16 |
| T28 | 4.1.7 | M23, M01, M14, M16 | V27, V28, V33; DOD17, DOD18 |
