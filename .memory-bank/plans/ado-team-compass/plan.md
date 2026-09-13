# Plano de implementação do ado-team-compass — v1.3

Data: 12/09/2026 · Complexidade L no núcleo / XL com integração remota · Track sugerido: FEATURE · Slug: ado-team-compass.

Planejamento standalone, sem execução de pipeline. Documentos complementares: [arquitetura](architecture.md) e [tarefas executáveis](task.md).

**Restrição obrigatória:** todo acesso ao Azure DevOps será exclusivamente pelo [MCP oficial Microsoft](https://github.com/microsoft/azure-devops-mcp). Proibidos REST/OData direto, SDK ADO e consultas por CLI como fallback. [Contrato e cobertura](../../../docs/ado-mcp-contract.md).

## 1. Missão

Entregar um plugin genérico para visibilidade de entrega no Azure DevOps, distribuível entre equipes, com cálculos auditáveis, interpretação curta e limitações explícitas. O produto deve funcionar com diferentes processos, sem exigir horas, tasks ou sprints de quem não usa essas práticas.

A primeira versão terá integrações locais para Claude Code, Google Antigravity e Codex (OpenAI/GPT), além de CLI sem LLM. GPTs personalizados no ChatGPT terão integração via Actions e API autenticada na v0.3.1. “GPT” é tratado como dois ambientes distintos; nenhum modelo específico é fixado. A promessa é responder o que está em andamento, onde existem riscos e que evidências sustentam ações; ausência de registro não será interpretada como ociosidade.

### 1.1 Releases e limites

| Release | Resultado | Fora desta release |
|---|---|---|
| v0.1 — situação atual distribuível | Instalação em Claude Code, Antigravity e Codex; setup, diagnóstico, carga condicional, visão entre equipes, JSON, Markdown e HTML operacional com recomendações | Histórico completo, previsão, publicação e escrita no ADO |
| v0.2 — histórico e planejamento | Compromisso, mudança de escopo, fluxo, regras de planejamento configuráveis | Forecast e operação agendada |
| v0.3 — operação | Pipeline de leitura via MCP oficial não interativo e retenção operacional | Hospedagem pública automática e alterações de work items |
| v0.3.1 — GPT personalizado | API de relatórios autenticada, OpenAPI e instruções para GPT Actions | Acesso anônimo, execução arbitrária e publicação em catálogo público |
| v0.4 — forecast experimental | Projeção com premissas, amostra e validação retrospectiva | Promessa de prazo garantido ou comparação de produtividade individual |

O HTML passa a ser entrega central da v0.1: [relatório de sprint e apoio à decisão](../../../docs/sprint-report.md).

A matriz detalhada está em [compatibilidade de plataformas](../../../docs/platform-compatibility.md). Compatibilidade aqui é requisito planejado, ainda não validado em execução.

Cada release tem critérios próprios; v0.1 pode ser usada sem esperar as demais. Features posteriores não devem virar pré-requisito da instalação inicial.

### 1.2 Indicadores de sucesso do produto

- Três equipes com práticas distintas conseguem usar o mesmo pacote sem alterar código.
- Um novo usuário conclui instalação e relatório de demonstração em até 15 minutos, com os pré-requisitos já disponíveis. Medir no piloto; não é tempo garantido de consentimento corporativo.
- Todo total e percentual exibido tem referência para a métrica e os fatos da execução.
- Uma equipe sem horas recebe diagnóstico e situação atual úteis, sem “falha de higiene” por campos não aplicáveis.
- Nenhuma coleta parcial aparece como visão completa; nenhuma permissão de escrita é exigida na v0.1.
- Cada achado do piloto é reconciliável com itens, política e período definidos. Divergências sem explicação bloqueiam a promoção da release.

## 2. Estado atual do sistema

### 2.1 Zona de trabalho

Pasta atual inspecionada: `pasta de planejamento original (fora deste repositório)`.

Antes deste planejamento havia apenas `work/` e `outputs/`; não foi encontrado código, infraestrutura de teste, repositório Git ou instruções locais de projeto. A proposta anexada e a crítica da conversa são as fontes de requisitos. Não foi acessada nenhuma organização ADO real.

A zona futura de implementação será um novo repositório do produto. Os caminhos da seção 4.3 são relativos à raiz desse repositório e representam **criações propostas**. Não criar o produto na pasta de instalação de outro plugin.

### 2.2 Convenções propostas

Python 3.12 como versão mínima inicial; validação em 3.12 e 3.13. Pacote com `pyproject.toml`, código tipado, pytest, Ruff e checagem estática com mypy. Dependências fixadas no lock da release. A seleção é uma decisão deste plano, não uma stack já existente.

CLI e schemas usam inglês para campos e identificadores; mensagens e relatórios começam em pt-BR. Labels ficam em catálogo para inclusão posterior de outros idiomas. Erros possuem código estável, mensagem acionável e detalhe sanitizado. Logs vão para stderr; JSON de automação não recebe texto misturado.

### 2.3 Contratos a preservar

N/A para compatibilidade preexistente: não há implementação. A partir de v0.1, configuração, manifesto de execução, schemas de métricas, códigos de saída e formato de evidências tornam-se contratos versionados. Alterações incompatíveis exigem nova versão de schema e migração ou erro explicativo; não reescrever silenciosamente execuções antigas.

### 2.4 Referências

Sem módulo interno similar. As decisões estão no documento de arquitetura. Integração MCP foi confrontada com o repositório e catálogo oficiais; versões e disponibilidade efetivas ainda serão verificadas pelos testes de contrato da implementação.

## 3. Definição de pronto

### 3.1 v0.1

- [ ] DOD01: pacote instala e roda em Windows, macOS e Linux em ambiente isolado; modo de demonstração funciona sem credencial e sem rede.
- [ ] DOD02: setup descobre equipes e metadados, valida configuração e registra capacidades disponíveis por equipe.
- [ ] DOD03: leitura usa somente o MCP oficial, verifica catálogo/schema e ações permitidas; falhas de autenticação, permissão, paginação e transporte têm saídas previstas sem fallback direto.
- [ ] DOD04: métricas distinguem ausência, zero, não aplicável, amostra vazia e coleta parcial; unidades incompatíveis não são somadas.
- [ ] DOD05: calendários e alocação passam nos cenários numéricos da seção 6, incluindo reservas duplicadas e ausência de disponibilidade global.
- [ ] DOD06: relatório determinístico rastreia números e mantém evidência completa fora do resumo do LLM.
- [ ] DOD07: narrativa não acrescenta números nem fatos sem referência e não afirma ociosidade, culpa ou causalidade não demonstrada.
- [ ] DOD08: testes automatizados, análise estática, build e checagem de pacote passam; testes de contrato/piloto têm evidências próprias. A infraestrutura de testes será criada em T01.
- [ ] DOD09: credenciais não aparecem em logs, fixtures ou artefatos; cache é isolado e retenção funciona.
- [ ] DOD10: release candidata passa no piloto com três perfis distintos e instalação em perfil limpo nos três hosts locais, pelos formatos suportados por cada um.

- [ ] DOD13: HTML operacional abre offline e mostra entrega, carga, gap, impedimentos e recomendações com evidência; filtros e exportação/importação de decisões preservam integridade.

### 3.2 Releases seguintes

- [ ] DOD11: métricas históricas preservam corte e definições; reaberturas, exclusões e falta de histórico aparecem explicitamente.
- [ ] DOD12: regras de planejamento são ativáveis por perfil e exibem política, evidência e exceções.
- [ ] DOD14: execução agendada é idempotente, observável e usa identidade própria, sem precisar manter chat aberto.
- [ ] DOD15: forecast é reproduzível e avaliado retrospectivamente antes de receber status estável.

- [ ] DOD16: Claude Code, Antigravity e Codex reproduzem as mesmas métricas para a mesma fixture, com instalação, atualização e remoção isoladas.
- [ ] DOD18: testes demonstram ausência de acesso ADO direto e bloqueio de ação não autorizada mesmo em ferramenta MCP mista.
- [ ] DOD17: GPT Actions consulta API HTTPS autenticada com autorização por equipe/usuário, sem exposição de credenciais ADO ou dados de outras equipes.

## 4. Especificação de implementação

### 4.1 Contratos e comportamento

#### 4.1.1 Entradas públicas

| Entrada da CLI | Comportamento |
|---|---|
| `setup` | Resolve organização/projetos/equipes, perfis e credencial; grava configuração local sem segredos |
| `doctor` | Diagnostica ambiente, acesso, configuração e capacidades disponíveis |
| `collect` | Coleta somente as fontes necessárias para escopo e período |
| `report` | Calcula e renderiza relatório a partir de uma coleta ou execução existente |
| `status` | Atalho para coleta atual e relatório de equipe |
| `allocation` | Visão de carga conhecida por pessoa/equipe, quando aplicável |
| `evidence` | Recupera detalhes locais por execução e referência, sem nova leitura indiscriminada do ADO |
| `replay` | Recalcula métricas com entradas congeladas e versão compatível |
| `demo` | Gera relatório usando dados sintéticos incluídos |
| `history`, `planning` | Entradas adicionais da v0.2 |
| `render`, `decisions` | HTML e exportação/importação explícita de decisões humanas na v0.1 |
| `run-scheduled` | Entrada adicional da v0.3 |
| `forecast` | Entrada experimental da v0.4 |

Opções comuns: configuração explícita, equipe por ID ou alias inequívoco, período, data de referência, formato, saída e modo offline. Sem equipe inequívoca, execução interativa pede seleção; execução não interativa encerra com erro de configuração. Não selecionar silenciosamente a primeira equipe encontrada.

Códigos de saída propostos: 0 = concluído com capacidades solicitadas atendidas; 2 = entrada/configuração inválida; 3 = autenticação ou acesso insuficiente ao escopo principal; 4 = falha de coleta sem relatório utilizável; 5 = relatório produzido, porém alguma capacidade solicitada está parcial ou indisponível; 6 = schema/versão incompatível. Métricas legitimamente não aplicáveis ao perfil não tornam a execução falha.

#### 4.1.2 Configuração

Configuração compartilhável: `.ado-team-compass/config.yaml`. Dados pessoais de disponibilidade e ajustes locais: `.ado-team-compass/config.local.yaml`, ignorado no Git. Um arquivo de exemplo sanitizado acompanha o produto.

Grupos obrigatórios no schema:

| Grupo | Campos e validações |
|---|---|
| Versão | `schema_version`; rejeitar major desconhecida |
| Conexões | alias, organização, servidor MCP oficial, transporte, versão/catálogo esperado e referência segura da sessão; nenhuma credencial de acesso ADO direto |
| Equipes | projeto e equipe por ID, nomes de exibição, perfil; várias equipes e projetos na mesma organização |
| Escopo | áreas e inclusão de descendentes, iterações, tipos de item e tratamento de bugs |
| Processo | campos de estimativa/trabalho, categoria dos estados, política de iniciado/concluído/bloqueado; objetivo da sprint e vínculos explícitos; origem de impedimentos e limites WIP |
| Calendário | timezone IANA, dias trabalhados, feriados, folgas e tratamento do dia atual |
| Carga | unidade, limiares, disponibilidade pessoal opcional e reservas por equipe |
| Histórico | corte de compromisso, coorte de itens, janela e política de reabertura |
| Planejamento | regras habilitadas, severidade, tolerâncias e exceções justificadas |
| Saída e retenção | diretório, idioma, limite do resumo, dias de retenção e seleção de campos |

Descobrir escopo e descendentes usando as ferramentas oficiais MCP disponíveis. Se a resposta não fornecer um atributo necessário, aceitar configuração explícita com proveniência ou marcar a análise indisponível; não consultar `teamfieldvalues` por API direta.

Três perfis iniciais: sprint com capacidade; sprint sem horas; fluxo contínuo sem sprint. Processo técnico descoberto não define sozinho o perfil de gestão. Mapeamentos ambíguos ficam desabilitados com motivo até configuração explícita.

#### 4.1.3 Artefatos de execução

| Artefato | Contrato mínimo |
|---|---|
| `run.json` | ID, versões, identidade opaca da fonte, início/fim da coleta, instante de referência, configuração efetiva sanitizada, hashes, estado da execução |
| `facts.json` | Pessoas, reservas, calendários, itens, relações, revisões necessárias e proveniência por fonte |
| `metrics.json` | ID da métrica, versão da definição, valor/unidade, período, status, cobertura e referências |
| `summary.json` | Métricas resumidas, achados prioritários, IDs, referências e indicador de truncamento |
| `evidence/` | Dados necessários para auditoria, minimizados e referenciados pelo manifesto |
| `report.md` | Tabelas determinísticas, limitações, evidências e narrativa validada quando disponível |
| `narrative.json` | Fatos referenciados, hipóteses e ações; ausente quando não houver LLM |
| `report.html` | Visão offline filtrável; números e referências derivados das mesmas métricas |
| `decisions.json` | Registro exportável/importável de ações humanas com IDs estáveis, run de origem, responsável/prazo informados e evidência; não altera snapshots |

Status de métrica: `available`, `partial`, `unavailable`, `not_applicable`. Uma amostra vazia conhecida recebe contagem zero quando isso fizer sentido; percentil sem amostra recebe valor nulo e motivo. Cobertura de campos é `valid / eligible`; denominador desconhecido gera cobertura desconhecida, nunca 100%.

Metadados de qualidade: quantidade elegível, conhecida, ausente, inválida, excluída; fonte e horário de coleta; motivos; lista de evidências. Cobertura de horas refere-se à contagem de itens estimáveis, não ao percentual de esforço total, que é desconhecido quando faltam estimativas.

O resumo terá alvo inicial de até 24 KiB de JSON UTF-8. Se exceder, manter totais e limitações, selecionar achados deterministicamente e fornecer referências para o restante. Nunca truncar fatos ou métricas de auditoria para caber no contexto.

#### 4.1.4 Regras numéricas da v0.1

**Tempo:** cálculo recebe `as_of` explicitamente. Eventos ficam em UTC; datas de calendário e fronteiras são resolvidas no timezone configurado. Iterações com fim inclusivo serão normalizadas para fim exclusivo. A API não deve ter datas de calendário deslocadas por conversão ingênua de meia-noite UTC.

**Dia atual:** modo padrão conservador exclui o dia corrente da capacidade restante e informa isso no relatório; opção explícita permite incluir o dia inteiro para planejamento matinal. Não ratear por hora do dia sem jornada intradiária configurada.

**Capacidade reservada:** soma da capacidade diária por atividade nos dias elegíveis, removendo a união de folgas de equipe, pessoais e feriados, sem desconto duplicado. Folgas parciais exigem informação local explícita quando a fonte não a fornecer.

**Carga conhecida:** soma de trabalho restante válido em itens abertos elegíveis. Ausente não vira zero; `OriginalEstimate` não substitui trabalho restante. Valor negativo é inválido e excluído com achado. Item concluído com trabalho restante positivo gera inconsistência; não entra automaticamente na carga aberta.

**Hierarquia:** usar um nível de contabilização definido no perfil; padrão para perfil de capacidade é task folha. Pai e filho nunca entram na mesma soma. Pai estimado com filhos sem estimativa gera limitação explícita, não desaparece silenciosamente. Bugs entram conforme comportamento e mapeamento da equipe.

**Unidades:** horas, dias ou unidade configurada são preservadas. Pontos não viram horas. Conversão dias→horas requer fator explícito e registra origem. Sem conversão, relatórios por unidade continuam disponíveis; agregação entre unidades é indisponível.

**Utilização observada:** carga restante conhecida / capacidade restante reservada na mesma janela e unidade. Se existem itens sem trabalho restante, o percentual é parcial e não sustenta classificação de baixa carga. Nenhuma imputação probabilística na v0.1.

**Classes padrão:** sem carga registrada; abaixo da faixa de referência (>0 e <0,60); dentro da faixa (0,60–0,90); atenção (>0,90–1,10); acima da faixa (>1,10). Fronteiras têm testes explícitos. Com dados incompletos, classe principal é `DADOS_INSUFICIENTES`; sobrecarga já demonstrada pela carga conhecida pode ser destacada como limite inferior. Com capacidade zero e carga positiva, usar `CARGA_SEM_CAPACIDADE`; zero/zero não produz percentual.

**Entre equipes:** deduplicar carga por organização + ID; apresentar itens sobrepostos como tal. Consolidar na mesma janela solicitada. Somar reservas não prova disponibilidade total. Disponibilidade global só é usada se explicitamente configurada para a pessoa e janela; não inferir 8 horas/dia. Sem isso, utilização global fica nula. Universo observado é a lista de equipes selecionadas e acessíveis; o plugin não promete conhecer todo o trabalho da pessoa.

**Recomendação:** transferência é candidata, nunca automática. Mesma Activity e folga estimada não demonstram habilidade, disponibilidade real ou ausência de dependências. Máximo de três ações sugeridas, cada uma com evidência e condição a confirmar.

#### 4.1.5 Histórico e planejamento da v0.2

Histórico será obtido exclusivamente pelas ferramentas de revisões/consultas do MCP oficial ou por snapshots locais anteriores coletados via esse MCP. Cobertura de itens excluídos, movidos e eventos intradiários precisa ser demonstrada. Não presumir suporte a Analytics/OData ou a snapshot histórico completo apenas por haver listagem de revisões.

| Métrica | Definição inicial e limites |
|---|---|
| Compromisso | Conjunto de requisitos elegíveis abertos em `commitment_at`; se não houver corte configurado, início local da sprint é baseline técnica explicitamente rotulada, sem alegar compromisso confirmado |
| Say/do | Itens da baseline concluídos no corte final / itens da baseline; sem baseline ou denominador zero, nulo; itens adicionados não entram no numerador |
| Mudança de escopo | Entradas e saídas separadas desde o corte; registrar eventos para identificar item que entrou e saiu dentro da sprint; não mostrar apenas saldo líquido |
| Carry-over da baseline | Itens da baseline não concluídos ao final / baseline; itens removidos continuam visíveis, com motivo quando houver; não confundir com itens efetivamente movidos para a próxima sprint |
| Pontos comprometidos | Valores congelados no corte; estimativas alteradas aparecem separadamente; não somar pontos entre equipes como produtividade comparável |
| Throughput | Contagem de itens únicos na primeira transição para concluído por período; conclusão posterior de item reaberto é registrada à parte, sem duplicar entrega nova |
| Cycle time | Tempo corrido entre primeira entrada em iniciado e primeira conclusão; coorte por primeira conclusão no período; reaberturas posteriores ficam em métrica própria |
| Lead time | Criação até primeira conclusão, na mesma coorte; nome deve explicitar que não é tempo até valor em produção |
| Aging WIP | Agora menos início do episódio aberto atual; se reaberto, episódio começa na reabertura; sem histórico, não estimar início pela última alteração genérica |
| Percentis | Método nearest-rank documentado, unidade de dias corridos, tamanho de amostra e janela publicados; sem amostra, nulo; com menos de 20 itens, indicar amostra pequena |
| Tendência | Séries descritivas por janela comparável; não concluir melhora/piora com regressão em seis pontos sem contexto e cobertura |

Consultas históricas e hidratação precisam referir-se ao mesmo corte. `ASOF` só pode ser usado quando a ferramenta MCP conectada o suportar e o teste demonstrar sua semântica; não chamar WIQL ou hidratação por REST diretamente. Sem cobertura, baseline/percentuais ficam indisponíveis. Snapshots locais permitem histórico a partir da primeira coleta, sem retroatividade inventada.

Regras de planejamento iniciais: datas invertidas; prazo vencido em item aberto; fim do pai anterior ao fim dos filhos quando a política exige isso; carga aberta em sprint encerrada; campos obrigatórios da política ausentes. Story sem task, estimativa ausente, divergência de área/iteração e trabalho em sprint futura ficam desabilitados por padrão. Cada achado: regra/versionamento, severidade, item, evidência, política, exceção e ação sugerida. Histórico de `CompletedWork` não é timesheet nem prova de produtividade.

#### 4.1.6 Visual, automação e forecast

v0.1: HTML operacional autocontido com SVG, filtros locais, cores acessíveis, tabelas equivalentes e nenhuma CDN. Seu contrato é [relatório de sprint](../../../docs/sprint-report.md); inclui gap atual de capacidade, impedimentos explícitos e ações candidatas. Variação de estimativa total, duração de bloqueios e gráficos históricos exigem coortes/cortes e entram na v0.2. Sem esses dados, os blocos são indisponíveis. Não inferir esforço realizado de CompletedWork sem política e período compatíveis.

Decisões humanas podem ser exportadas e importadas explicitamente pelo núcleo; sem sincronização remota do HTML e sem escrita no ADO. v0.3: operação agendada e entrega de artefatos. Publicação inicial em artefato privado de pipeline escolhido na implantação; não prometer URL pública estável. Hook de sessão é opcional, somente consulta metadados locais e não coleta nem autentica automaticamente.

Execução agendada usa chave por configuração + equipe + janela + data, lock contra duplicação e marcador de sucesso. Falha não substitui relatório válido por relatório vazio. Notificações só na mudança relevante ou falha acionável, com canal configurado e autorização do operador. Templates são entregáveis; ativação e postagem são ações futuras separadas.

v0.4: forecast sobre itens comparáveis de uma equipe, escopo restante explícito, throughput incluindo períodos sem entrega e semente registrada. Sem histórico suficiente, negar projeção e mostrar o requisito faltante. Regra experimental inicial: ao menos 12 semanas completas e 30 conclusões comparáveis; é um limite de produto, não garantia estatística. Backtesting com cortes sem vazamento de futuro; publicar cobertura empírica de p50/p85 e cenários de escopo. Não juntar throughput de equipes diferentes nem converter pontos em itens arbitrariamente.

#### 4.1.7 Integrações de plataformas

A fonte das instruções e referências será `integrations/shared/`; o empacotamento gera bundles autocontidos, sem links externos ao diretório instalado. Fórmulas, contratos e templates ficam no núcleo. Variáveis, manifestos, comandos e hooks específicos de um host não entram nas instruções compartilhadas.

- Claude Code: manter o pacote existente no plano e seu manifesto próprio.
- Antigravity: pacote com `plugin.json` na raiz e skills; alternativa de skills no workspace documentada. Validar a versão real do IDE e não prometer paridade de CLI, SDK ou hooks sem testes.
- Codex: pacote dedicado com `.codex-plugin/plugin.json` e skills; instalação testada nas superfícies locais suportadas. Não assumir que um manifesto Claude funciona sem adaptação, nem que a extensão de IDE suporta o pacote.
- GPT personalizado: um adaptador HTTP de leitura disponibiliza relatórios já produzidos pelo motor. O GPT recebe instruções e schema OpenAPI, não scripts locais. Não adicionar chamada de modelo OpenAI ao núcleo apenas para suportar o host.

Contrato remoto inicial: listar equipes permitidas, obter último relatório por equipe e consultar evidência por execução. Somente GET; sem disparar jobs longos nem oferecer terminal ou acesso arbitrário a URLs. Relatório ausente retorna 404; antigo mantém timestamp e aviso; nunca fabricar atualização. A coleta é executada separadamente por T23.

Segurança remota: implantação dedicada por organização, OAuth por usuário e ACL de equipes no servidor, negativa por padrão, validação de emissor/audiência e autorização em toda consulta inclusive por run ID. O coletor acessa ADO exclusivamente pelo MCP oficial; sua conexão autentica conforme o servidor suportar; token do GPT autoriza somente a API. Revogação de usuário e alteração de ACL precisam valer na requisição seguinte. Links de artefato também exigem autorização. Não aceitar equipe/org arbitrária enviada pelo modelo como autorização.

Dependências de T28: API com FastAPI/Uvicorn como extra opcional, provedor OAuth corporativo, domínio HTTPS alcançável pelo ChatGPT e armazenamento dos relatórios sanitizados. Fixar versões no lock na implementação; não criar infraestrutura ou publicar dados nesta revisão. A primeira topologia remota usa um serviço por organização, uma instância de leitura e volume de relatórios com escrita atômica pelo coletor; SaaS multi-tenant continua fora de escopo. Disponibilidade de Actions depende do plano e das políticas do workspace do usuário, a validar no teste de integração.

### 4.2 Fluxo de execução e fases

Fluxo da v0.1: validar entrada → resolver identidade/configuração → verificar capacidades necessárias → coletar escopo autorizado → normalizar e registrar cobertura → calcular com relógio fixado → persistir execução completa por escrita atômica → gerar relatório determinístico → gerar/validar narrativa opcional → retornar artefatos e status.

| Fase | Tarefas | Entrega verificável | Dependência | Esforço estimado |
|---|---|---|---|---|
| F0 — Contratos e pacote | T01–T02 | Instalação de desenvolvimento, schemas e demo mínima | Nenhuma | 3–5 dias-pessoa |
| F1 — Acesso e coleta | T03–T06 | Diagnóstico e fatos normalizados com cobertura | F0 | 6–10 dias-pessoa |
| F2 — Métricas atuais | T07–T10 | Qualidade por métrica, calendário, carga e visão entre equipes | F1; cálculos podem iniciar com fixtures de F0 | 6–10 dias-pessoa |
| F3 — Relatório e integrações | T11–T13, T22, T26–T27 | Execução auditável, HTML de decisão, Markdown e três bundles locais | F2 | 15–25 dias-pessoa |
| F4 — Distribuição e piloto | T14–T16 | Release candidata validada em três perfis | F3 | 6–10 dias-pessoa |
| F5 — Histórico e planejamento | T17–T21 | v0.2 com semântica e evidências históricas | v0.1 | 16–25 dias-pessoa |
| F6 — Operação | T23–T24 | v0.3 com execução agendada testada | v0.2 para relatório completo | 4–7 dias-pessoa |
| F6b — GPT personalizado | T28 | API autenticada e GPT Actions validados | T24 e ambiente remoto | 8–14 dias-pessoa |
| F7 — Forecast experimental | T25 | v0.4 com backtesting | T17, T20, T21 | 5–9 dias-pessoa |

v0.1: **36–60 dias-pessoa**. Demais releases, incluindo GPT Actions: **33–55 dias-pessoa**. Total de escopo planejado: **69–115 dias-pessoa**. São faixas de planejamento, incluindo testes e documentação, não orçamento contratado. Espera por credenciais, revisão corporativa ou disponibilidade do piloto é tempo de calendário adicional. Para uma pessoa em dedicação integral, v0.1 representa aproximadamente 8–12 semanas úteis. Reestimar após F1 e depois do primeiro time piloto; não comprimir por simples divisão pelo número de agentes.

Caminho crítico: contratos → autenticação/escopo/coleta → qualidade e capacidade → relatório → integração instalada → piloto. Paralelismo possível após T02: calendário e fórmulas sobre fixtures enquanto leitura externa é implementada; testes de narrativa e empacotamento após estabilizar saída. Nenhum trabalho paralelo altera o schema sem sincronizar consumidores.

### 4.3 Mapa de alterações proposto

Todos os itens abaixo são **CRIAR** em repositório novo. Áreas agrupadas permitem arquivos auxiliares internos, sem mudar responsabilidade. Artefatos de planejamento e anexos originais devem ser preservados. Não há arquivo de produto preexistente para modificar.

| ID | Caminho ou área proposta | Conteúdo e motivo | Tarefas |
|---|---|---|---|
| M01 | `pyproject.toml`, `uv.lock`, `.gitignore`, `src/ado_team_compass/__init__.py` | Pacote, dependências e exclusões seletivas; extra opcional da API | T01, T15, T28 |
| M02 | `src/ado_team_compass/cli.py`, `errors.py` | Entradas, códigos de saída e mensagens | T01, T03, T11, T13, T17, T19, T22, T23, T25 |
| M03 | `src/ado_team_compass/contracts/`, `schemas/` | Modelos de configuração, fatos, métricas, narrativa, decisões e manifesto | T02, T12, T17, T22, T25 |
| M04 | `src/ado_team_compass/config/`, `profiles/`, `examples/config/` | Resolução de configuração, perfis e exemplos | T02, T04, T07, T08, T19, T23 |
| M05 | `src/ado_team_compass/mcp/session/` | Sessão, autenticação do transporte MCP e diagnóstico; sem provedor ADO direto | T03, T23 |
| M06 | `src/ado_team_compass/adapters/ado_mcp/` | Cliente MCP oficial, catálogo, ações de leitura, paginação e histórico suportado | T03–T06, T17 |
| M07 | `src/ado_team_compass/collect/`, `normalization/` | Fatos, relações, cobertura e deduplicação | T05, T06, T10, T17 |
| M08 | `src/ado_team_compass/metrics/quality.py` | Disponibilidade por métrica | T07 |
| M09 | `src/ado_team_compass/metrics/calendar.py`, `allocation.py`, `cross_team.py` | Calendários, carga e visão entre equipes | T08–T10 |
| M10 | `src/ado_team_compass/runs/` | Persistência, hashes, replay, retenção, lock e migração | T06, T11, T14, T23 |
| M11 | `src/ado_team_compass/reporting/`, `templates/`, `locales/` | Markdown, interpretação, HTML e linguagem | T11, T12, T19, T21, T22, T25 |
| M12 | `plugin/claude/.claude-plugin/plugin.json`, `plugin/claude/skills/`, `plugin/claude/bin/` | Pacote completo da integração; inclui wheel/lock necessários no processo de release | T13, T15, T21, T22 |
| M13 | `.claude-plugin/marketplace.json`, `packaging/` | Catálogo, configuração MCP por host e criação de bundle instalável | T13, T15, T26, T27 |
| M14 | `tests/unit/`, `tests/fixtures/`, `tests/contract/`, `tests/integration/`, `tests/evals/`, `tests/install/` | Suítes e dados sintéticos; cada tarefa testa sua responsabilidade | T01–T28 conforme rastreabilidade |
| M15 | `.github/workflows/ci.yml`, `.github/workflows/release.yml` | Qualidade e release candidata | T01, T14, T15 |
| M16 | `README.md`, `CHANGELOG.md`, `docs/` | Instalação, definições, limitações, piloto, compatibilidade e suporte | T01–T28 conforme entrega |
| M17 | `src/ado_team_compass/metrics/commitment.py`, `flow.py` | Coortes, baseline de escopo/esforço, variações, filas, impedimentos, séries e percentis | T18, T20 |
| M18 | `src/ado_team_compass/metrics/planning.py`, `rules/` | Políticas e achados de planejamento | T19 |
| M19 | `automation/`, `plugin/claude/hooks/` | Templates de pipeline e aviso local opcional | T23, T24 |
| M20 | `src/ado_team_compass/metrics/forecast.py`, `tests/backtesting/` | Simulação e avaliação retrospectiva | T25 |
| M21 | `integrations/shared/`, `plugin/antigravity/`, `packaging/antigravity/` | Fonte comum de instruções e bundle Antigravity | T13, T26, T15, T21, T22 |
| M22 | `plugin/codex/`, `packaging/codex/` | Bundle Codex e manifesto próprio | T27, T15, T21, T22 |
| M23 | `integrations/chatgpt/`, `src/ado_team_compass/gateway/`, `automation/gateway/` | OpenAPI, instruções GPT, API de leitura autenticada e implantação dedicada | T28 |
| M24 | `src/ado_team_compass/decisions/` | Candidatos de ação determinísticos, registro humano, exportação/importação e rastreabilidade | T22, T21 |

### 4.4 Dependências técnicas e operacionais

Runtime proposto: SDK cliente MCP Python com versão fixada para transportar chamadas ao servidor oficial, `pydantic` para modelos/schemas, `PyYAML` com carregamento seguro, `Jinja2` para saída determinística e `tzdata` para portabilidade. CLI pode usar biblioteca padrão; evitar framework adicional sem necessidade. Desenvolvimento: pytest, Ruff, mypy e build. `uv` gerencia ambiente e lock; alternativa via venv documentada.

Não há versões instaladas para reutilizar. Fixar versões exatas e hashes compatíveis em T01; não usar dependência flutuante na release. Monte Carlo pode usar biblioteca padrão com semente; uma nova dependência numérica exige justificativa em T25.

Variável prevista: `ADO_TEAM_COMPASS_CONFIG` para caminho. Conexão e autenticação usam configuração segura do cliente MCP oficial; nenhuma variável `ADO_PAT` como fallback do produto. Versões do servidor local são fixadas; catálogo remoto é verificado por handshake/listagem de ferramentas e hash de schema. O coletor não depende de versões REST/OData próprias.

Dependências externas para piloto: identidade com leitura das equipes selecionadas; três equipes representando os perfis; disponibilidade pessoal validada para testar percentual global; ferramentas MCP de histórico e cobertura suficiente para v0.2. Sua ausência não impede testes sintéticos, mas impede declarar validação real correspondente.

## 5. Guardrails de implementação

1. Sem cálculo de domínio pelo LLM; arredondar apenas na apresentação e conservar valores de origem.
2. Sem comparar estado por strings fixas globais; mapear categoria e política local. Estado desconhecido invalida métricas dependentes.
3. Sem trocar ausência por zero, estimativa original por restante ou pontos por horas.
4. Sem percentual de confiança inventado a partir de score de higiene.
5. Sem atribuir produtividade, culpa ou ociosidade real a partir dos registros.
6. Sem coletas globais implícitas nem tentativas de contornar 403. Escopo e cobertura acompanham a execução.
7. Sem registrar tokens ou campos sensíveis desnecessários; título/descrição de item não pode alterar instruções, executar comandos ou escolher destinos de saída.
8. Sem persistir estado mutável no cache de instalação do plugin. Configuração e dados de execução ficam fora dele.
9. Sem executar escrita no ADO na v0.1–v0.4 planejada. Allowlist por ferramenta e ação MCP; não confiar no nome da ferramenta como garantia de leitura. Toda futura escrita também passa pelo MCP oficial.
10. Sem sobrescrever execuções anteriores nem promover release com teste real não realizado declarado como aprovado.
11. Retentativas limitadas por orçamento de tempo; respeitar `Retry-After` quando presente, com backoff/jitter. Concorrência inicial máxima quatro, ajustável e limitada.
12. Mudar plano e schemas antes de ampliar escopo; não implementar Jira, serviço central ou ranking individual como “melhoria” incidental.

## 6. Estratégia de testes

Infraestrutura inexistente será criada em T01. As expectativas numéricas precisam ser calculadas e revisadas independentemente da implementação; golden files sozinhos apenas congelam comportamento, inclusive bugs.

| Cenário | Resultado obrigatório | Tarefas |
|---|---|---|
| V01 — 5 dias úteis, 6 unidades/dia, 1 folga | Capacidade 24; feriado sobreposto à mesma folga não reduz para 18 | T08 |
| V02 — 16 de carga conhecida e duas tasks sem restante | Total conhecido 16, ausências 2, classificação de baixa carga impedida | T07, T09 |
| V03 — OriginalEstimate 40, restante ausente | Nunca apresentar 40 como trabalho restante | T09 |
| V04 — 6 horas/dia em dois times, disponibilidade pessoal 6, cinco dias | Reservas 60 versus disponibilidade 30; apontar sobre-reserva | T10 |
| V05 — Mesmo cenário sem disponibilidade pessoal | Reservas visíveis, utilização global nula | T10 |
| V06 — Mesmo ID retornado por duas áreas/times | Carga global contada uma vez; sobreposição demonstrada | T05, T10 |
| V07 — Capacidade zero com carga positiva; zero com zero | Classe de carga sem capacidade; nenhum infinito ou divisão inválida | T09 |
| V08 — Dias e horas sem conversão | Totais separados e agregado indisponível | T08–T10 |
| V09 — Pai e tasks filhos estimados | Contabilizar só o nível definido; não somar ambos | T05, T09 |
| V10 — Time Kanban sem tasks, horas ou sprints | Situação atual funciona; carga/sprint não aplicáveis | T04, T07, T16 |
| V11 — Erro MCP de autenticação/permissão, paginação incompleta, limite e timeout | Erro acionável ou resultado parcial; nunca zero silencioso nem bypass de MCP | T03, T05, T06 |
| V12 — Fronteiras de datas, timezone e dia atual | Mesmo instante e política produzem mesma janela, inclusive no limite da sprint | T08 |
| V13 — Nome/área renomeada e estados customizados | IDs preservam identidade; desconhecidos não são classificados por palpite | T04, T05 |
| V14 — Execução repetida com fatos/versões congelados | Métricas idênticas, independentemente do horário real de replay | T11, T14 |
| V15 — Título contendo instrução e marcação HTML | Tratado como texto; não executa ação e é escapado na renderização | T12, T22 |
| V16 — Narrative com ID ou percentual inexistente | Rejeitar trecho e manter relatório determinístico utilizável | T12, T13 |
| V17 — Corte histórico seguido de mudança de pontos/área | Baseline congelada; valores atuais não contaminam passado | T17, T18 |
| V18 — Item concluído, reaberto e concluído novamente | Uma nova entrega na definição inicial; reabertura contabilizada separadamente | T20 |
| V19 — Item entra e sai da sprint; baseline vazia | Entrada/saída visíveis; say/do nulo com denominador zero | T18 |
| V20 — Feature entre áreas e story sem task com regra desativada | Nenhum falso achado dessas políticas | T19 |
| V21 — Instalação, atualização e rollback em perfil limpo | Plugin encontra o motor correto; dados locais preservados | T15, T16 |
| V22 — Duas execuções agendadas simultâneas e falha posterior | Sem duplicação de resultado final; sucesso anterior preservado | T23, T24 |
| V23 — Semanas de throughput zero e amostra insuficiente | Zeros preservados; forecast negado se requisito mínimo falhar | T25 |
| V24 — Histórico com cortes de backtesting | Treino só usa passado de cada corte; semente reproduz distribuição | T25 |
| V25 — Mesma fixture nos três hosts locais | Métricas iguais; diferenças de prosa permitidas; mesma política para dados parciais | T13, T26, T27, T14 |
| V26 — Instalar/atualizar/remover um bundle com outros presentes | Sem sobrescrever configuração alheia; nenhuma variável exclusiva de outro host nas skills | T15, T26, T27 |
| V27 — GPT com token ausente, expirado ou sem acesso à equipe/run | 401/403 e nenhuma evidência vazada; alterar ID não contorna ACL | T28 |
| V28 — GPT consulta relatório antigo, inexistente ou grande | Data/limitação explícita, 404 para ausente, paginação/limites e mesmos totais da CLI | T28 |

Testes de contrato usam respostas sanitizadas e falhas simuladas; integração real é opt-in, com credenciais fora do CI público. CI padrão executa tudo que é determinístico sem rede. Evals da skill incluem perguntas naturais em português, pedidos de ranking, contexto contraditório e evidência parcial.

Meta inicial de desempenho: fixture de 2.000 itens atuais e 100 pessoas gera métricas e Markdown offline em até 5 segundos em executor de referência documentado. Testar também resumo acima do limite. Tempo do MCP oficial é medido separadamente; não prometer latência fixa dependente do ADO.

## 7. Riscos, assunções e decisões

### 7.1 Riscos

| Risco | Impacto | Tratamento |
|---|---|---|
| Acesso corporativo/consentimento | Bloqueia piloto, não desenvolvimento sintético | T03 registra identidade e requisito faltante; piloto com responsável |
| Capacidade não mantida | Classificação enganosa | Qualidade por métrica e limite explícito |
| Equipes com áreas sobrepostas | Dupla contagem | Identidade por item e atribuição de pertencimento separado |
| Histórico insuficiente ou itens excluídos | Séries incompletas | Cobertura histórica e indicação de indisponibilidade |
| Mudança de processo ou equipe | Comparação temporal inválida | Versão de configuração e quebra de série documentada |
| Atualização do plugin | Motor/schema incompatíveis | Contrato de versões, migração explícita e rollback |
| Distribuição em Windows/proxy corporativo | Instalação falha | Matriz de instalação e diagnóstico; sem desabilitar TLS |
| Relatório com nomes/dados internos compartilhado indevidamente | Exposição de informações | Minimização, armazenamento local e publicação privada separada |
| Escopo de 28 tarefas crescer antes do piloto | Atraso sem aprendizado | Promover v0.1 antes de iniciar expansão opcional |

### 7.2 Defaults de planejamento

| ID | Default | Justificativa | Impacto se mudar |
|---|---|---|---|
| A01 | Claude Code + Antigravity IDE + Codex locais; GPT Actions remoto | Pedido explícito de compatibilidade adicional | Host remoto exige infraestrutura própria; modelos continuam livres |
| A02 | Azure DevOps Services primeiro | URLs e autenticação da proposta são cloud | Server exige matriz própria de compatibilidade |
| A03 | Uma organização por consolidação | Evita identidade implícita entre tenants | Nova fase de identidade e escopo |
| A04 | pt-BR na saída e inglês nos contratos | Idioma do pedido e estabilidade técnica | Adicionar catálogo, preservando schemas |
| A05 | Execução local; 30 dias de retenção | Limita operação e volume inicial | Ajuste configurável; retenção maior ocupa disco |
| A06 | Dia corrente excluído da capacidade restante | Evita prometer o dia inteiro no fim da tarde | Opção explícita altera comparação e fica registrada |

Esses defaults estão expostos para revisão, não são preferências previamente confirmadas além do contexto indicado. O repositório privado é `LuisCarlosLopes/ado-team-compass`. Licença para eventual publicação pública, equipes piloto e domínio/provedor OAuth para T28 não foram definidos: são requisitos operacionais de T16 para liberação externa, não impedem construir o candidato local.

### 7.3 Registro de decisões

| Tipo | Decisão | Evidência | Status |
|---|---|---|---|
| Descoberta | Produto novo, sem código a preservar | Inspeção da pasta atual | Resolvido |
| Inferível do pedido | Gestão por dados ADO, múltiplas equipes e distribuição | Proposta + crítica solicitada | Resolvido |
| Arquitetura | Python/CLI, integração fina, leitura e métricas condicionais | D01–D08 e trade-offs | Resolvido para este plano |
| Implementação | Fórmulas, janela, persistência e testes | Seção 4 e cenários numéricos | Resolvido para este plano |
| Default explícito | Host, cloud, idioma e retenção | A01–A06 | Default aplicado |
| Operacional futuro | Destino/licença, acesso real e responsáveis de piloto | Não fornecidos | Pré-condição de publicação/piloto, sem inventar valores |

## 8. Protocolo de autocorreção e validação

Antes de concluir cada tarefa, conferir comportamento, contratos, escopo, testes e evidências. Corrigir divergências numéricas pela regra documentada; não ajustar fixture para aceitar a implementação sem revisar o cálculo independente. Quando um campo real contradizer a premissa, registrar decisão e atualizar schema, plano e testes relacionados.

Revisão deste planejamento: cruzar IDs do mapa com tarefas, verificar ausência de dependências cíclicas, cobrir todos os cenários V01–V33 e DOD01–DOD18, confirmar que releases não dependem de publicação futura para rodar localmente. O plano não declara testes de produto executados.

## 9. Entrega, rollout e handoff

Cada conclusão de tarefa deve registrar: áreas alteradas; resultado observável; testes executados e resultado; limitações; mudanças de contrato e documentação. Atualizar o status no checklist somente com evidência.

Rollout v0.1: demo sintética → um time com capacidade → time sem horas → time de fluxo contínuo → instalação de candidato em perfil limpo → release estável no destino escolhido. Em cada piloto, revisar uma amostra fixa de 20 itens ou todos quando houver menos; comparar totais completos por consulta equivalente e explicar diferenças com o board.

Rollback: reinstalar versão anterior do plugin/motor; manter execuções antigas imutáveis; backup de configuração antes de migração. Se a versão antiga não entender a configuração nova, restaurar backup explícito. Nunca corrigir problema do relatório alterando automaticamente os work items.

A primeira tarefa executável é T01. O plano autoriza a sequência técnica como especificação; a solicitação atual é somente produzir o planejamento. Publicação, instalação no ambiente pessoal e acesso a dados reais não foram realizados.

## 10. Metadados

| Campo | Valor |
|---|---|
| Versão | 1.3 |
| Artefato canônico | `.memory-bank/plans/ado-team-compass/plan.md` |
| Complexidade | L no núcleo local; XL no escopo completo com gateway remoto |
| Score de complexidade | 6: múltiplos módulos 1 + arquitetura 2 + dependências 1 + validação 1 + aceite complexo 1; sem efeito irreversível no escopo de construção |
| Track sugerido | FEATURE, usado apenas para calibragem |
| Confiança da classificação | Alta; escopo textual e estrutura nova conhecidos |
| Rubrica de completude do planejamento | 90/100: escopo 20, arquitetura 15, alvos novos mapeados e ausência verificada 20, contratos 15, padrão de testes preexistente 0, decisões de construção 20 |
| Limite da rubrica | Não mede probabilidade de sucesso nem validação do ADO real; aplicação adaptada a projeto novo |
| Infraestrutura de testes | Criada em T01; 434 testes determinísticos sem rede e sem credencial |
| Áreas de criação propostas | 24; quantidade final de arquivos será definida dentro dessas áreas |
| Tarefas | 28: 21 concluídas, 6 parciais e 1 bloqueada (T16, piloto real) |
| Migração de banco | Não; migrações futuras são de configuração/schema |
| Estado de execução | Implementado e verificado localmente em 13/09/2026; sem conexão real ao Azure DevOps, sem instalação nos hosts e sem piloto (T16 bloqueada) |

## 11. Fontes técnicas e uso

Consultadas em 12/09/2026. As fórmulas e limites deste documento são decisões do produto; não atribuir sua validação à documentação do fornecedor.

- [Plugins Claude Code](https://code.claude.com/docs/en/plugins-reference): estrutura e resolução de componentes.
- [Marketplaces Claude Code](https://code.claude.com/docs/en/plugin-marketplaces): distribuição do pacote por catálogo Git.
- [Skills Claude Code](https://code.claude.com/docs/en/skills): entradas e argumentos da integração.
- [MCP oficial Azure DevOps](https://github.com/microsoft/azure-devops-mcp): canal exclusivo de acesso e modos de conexão oficiais.
- [Capacidade no Azure Boards](https://learn.microsoft.com/en-my/Azure/devops/boards/sprints/set-capacity?view=azure-devops): unidade e capacidade por equipe.
- [WIQL](https://learn.microsoft.com/th-th/azure/devops/boards/queries/wiql-syntax?view=azure-devops): consulta histórica ASOF.

## 12. Revisão 1.1 — compatibilidade ampliada

Solicitação incorporada: Antigravity e GPT, preservando Claude Code. T26 e T27 entram antes de T14, embora seus IDs sejam maiores, para manter a rastreabilidade da versão anterior. T28 adiciona GPT personalizado depois da operação agendada. Alterações de integração não modificam fórmulas. Documento adicional: [matriz e contratos por plataforma](../../../docs/platform-compatibility.md).

## 13. Revisão 1.2 — relatório de sprint como entrega central

T22 passa da v0.3 para F3/v0.1, com contrato detalhado de capacidade, desvios, gargalos, impedimentos e recomendações. T14 depende de T22; T21 enriquece o mesmo HTML com histórico. O estudo prioriza objetivo/entrega, gap atual e desbloqueio, sem ranking individual. Escrita no ADO permanece fora de escopo; registro humano de decisões é local e explícito.

Cenários adicionais obrigatórios:

| ID | Cenário e resultado esperado | Tarefas |
|---|---|---|
| V29 | Carga 144 h, capacidade restante 120 h, três itens sem restante: gap conhecido +24 h, 120% parcial; não inventar carga total nem data de atraso | T22, T14 |
| V30 | Sem baseline ou CompletedWork não comparável: variação de esforço indisponível; não atribuir acumulado de sprints anteriores à atual | T18, T21, T22 |
| V31 | Fila grande sem histórico ou item sem alteração: indício/idade desconhecida, nunca impedimento ou causa comprovados por inferência | T20, T21, T22 |
| V32 | Exportar decisão, importar em nova execução e reaparecer achado: ID estável, origem humana e deduplicação; filtro não modifica total global sem rótulo | T22, T14 |

## 14. Revisão 1.3 — ADO exclusivamente via MCP oficial

Substitui as decisões anteriores de REST/OData, autenticação ADO própria e MCP opcional. A topologia é host/cliente MCP → servidor oficial → respostas estruturadas → motor Python → JSON/HTML. Gateway GPT apenas lê relatórios produzidos por essa cadeia. Falta de capacidade do servidor limita a funcionalidade; não autoriza conector alternativo.

| ID | Cenário e resultado esperado | Tarefas |
|---|---|---|
| V33 | Ferramenta ausente/renomeada, schema incompatível ou ação de escrita dentro de ferramenta mista: recusar operação, identificar limitação e não realizar chamada REST/OData/SDK/CLI ADO; offline funciona sem rede | T03, T14, T17, T23, T28 |

Esforços anteriores são estimativas condicionais ao catálogo MCP conectado. Reestimar após T03/T04 com cobertura e limites medidos; nenhum prazo implica disponibilidade de histórico ou autenticação não interativa não comprovados. [MCP oficial e matriz de cobertura](../../../docs/ado-mcp-contract.md).
