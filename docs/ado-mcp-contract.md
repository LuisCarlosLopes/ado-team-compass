# Contrato de acesso ao Azure DevOps — v1.3

## Regra obrigatória

**Toda comunicação do ADO Team Compass com o Azure DevOps será feita exclusivamente pelo MCP oficial da Microsoft: [microsoft/azure-devops-mcp](https://github.com/microsoft/azure-devops-mcp).**

Vale para descoberta, equipes, iterações, capacidade, itens, relações, consultas, histórico e qualquer futura ação autorizada. O escopo atual permanece somente de leitura. Não usar APIs REST/Analytics/OData diretamente, SDK ADO, CLI para consultar ADO, scraping ou MCP alternativo como fallback.

O servidor oficial pode acessar APIs internamente; isso não autoriza o produto a duplicar seu transporte. O motor Python recebe respostas estruturadas do MCP, normaliza fatos, calcula métricas e gera JSON/Markdown/HTML. Demo e replay podem operar offline com evidências já coletadas; anotações humanas são identificadas separadamente.

## Topologia e distribuição

Host ou executor → cliente MCP → servidor oficial Microsoft → respostas/evidências → motor determinístico → relatórios.

O README oficial recomenda o servidor remoto; a distribuição local oficial é alternativa para cenários que precisam de stdio. Usar o formato de configuração apropriado a Claude Code, Antigravity ou Codex, sem copiar configuração de outro host literalmente. Fixar versão do pacote local e validar catálogo remoto na conexão.

Não pressupor que o MCP disponível no chat seja automaticamente acessível a um subprocesso Python. O executor precisa de sua própria sessão MCP oficial suportada, ou de um mecanismo do host que encaminhe respostas estruturadas sem transcrição/resumo do LLM. T03 deve demonstrar essa passagem com fixture e conexão real. Nunca pedir ao modelo para copiar centenas de campos manualmente como mecanismo de transporte auditável.

GPT Actions acessa somente a API de relatórios do produto. O coletor desses relatórios também usa o MCP oficial; o gateway não implementa acesso próprio ao ADO. Autenticação da API de relatórios e autenticação MCP são fronteiras separadas.

## Catálogo verificado em conexão real — 13/09/2026

Handshake executado contra `@azure-devops/mcp@2.10.0` por stdio, organização `llopes`,
autenticação PAT mantida pela configuração de MCP do host. Catálogo com **40 ferramentas**,
hash `sha256:cf8ab09bf1e2bdd1d53a36db79acb736`. As 11 operações de leitura do produto foram
resolvidas.

| Operação lógica | Ferramenta : ação (verificada) |
|---|---|
| Projetos | `core_list_projects` |
| Equipes | `core_list_project_teams` |
| Configuração da equipe | `work` : `get_team_settings` |
| Iterações | `work` : `list_team_iterations` |
| Capacidade da equipe | `work` : `get_team_capacity` |
| Capacidades da iteração | `work` : `get_iteration_capacities` |
| Itens da iteração | `wit_work_item` : `list_for_iteration` |
| Hidratação em lote | `wit_work_item` : `get_batch` |
| Tipo de item | `wit_work_item` : `get_type` |
| Revisões | `wit_work_item` : `list_revisions` |
| Consulta salva | `wit_query` : `get_results` |

### Comportamentos do servidor que mudaram a implementação

1. **Ferramentas consolidadas por ação.** A autorização passou a ser por ferramenta **e**
   ação. `wit_backlog` é mista (`list` e `list_work_items` são leitura, `reorder` é escrita) e
   por isso nunca é resolvida: a allowlist recusa o par por verbo de escrita.
2. **Envelope de conteúdo não confiável.** Cada bloco vem entre delimitadores
   `<<hash>> [UNTRUSTED ...] <<hash>>`. O produto remove o envelope para ler os dados, registra
   que ele existia e continua tratando todo conteúdo como dado, nunca como instrução.
3. **Resposta em múltiplos blocos.** O contexto da chamada vem em um bloco de texto e os dados
   em outro. Interpretar só o primeiro bloco devolvia o eco do contexto; hoje cada bloco é
   desembrulhado separadamente.
4. **Resposta sem dados estruturados é erro de coleta.** Um eco de contexto jamais vira
   contagem zero: a operação falha com `E_MCP_RESPOSTA_NAO_ESTRUTURADA` e a execução fica parcial.
5. **Hidratação exige `fields`.** Sem a lista explícita, o lote devolve um conjunto mínimo sem
   trabalho restante. O produto pede os campos de sistema mais os configurados no perfil.
6. **Identidade da pessoa em dois formatos.** A capacidade traz `id` (GUID), `uniqueName` e
   `displayName`; o item traz `"Nome <conta>"`. A coleta reconcilia pelo índice construído a
   partir da capacidade; sem correspondência, o achado é registrado em vez de duplicar a pessoa.
7. **Revisões exigem `workItemId`.** O parâmetro `id` pertence a outra ação e é recusado.
8. **Estados e campos vêm do processo.** `get_type` devolve estados com categoria e a lista de
   campos; o setup usa isso para mapear `state_categories` e os campos de agendamento, em vez
   de pedir mapeamento manual.
9. **Configuração da equipe traz escopo e calendário.** `areaPaths`, `workingDays` (0 = domingo,
   convertido para o padrão do Python) e `bugsBehavior` alimentam escopo, dias úteis e
   tratamento de bugs.
10. **Folga de equipe não é exposta.** A capacidade traz folgas pessoais; folgas de equipe não
    vieram na resposta, então a fonte `team_days_off` fica parcial com motivo.

### Reconciliação da primeira coleta real

Projeto `demo-ado-plugin`, iteração `Sprint 2 Checkout`: 18 itens na iteração, 15 no nível de
contabilização (3 pais excluídos), 12 abertos, 11 com trabalho restante somando **126 h**,
1 item sem valor, 1 item impedido pela tag configurada. Uma consulta independente sobre as
mesmas respostas reproduziu exatamente esses números, e o replay devolveu métricas idênticas.

## Catálogo documentado anteriormente e limites

Referência documental consultada: commit `9a81b90b67623ebc68c25b281d7fbf4f6e791eb0` do repositório oficial. [Catálogo nessa revisão](https://github.com/microsoft/azure-devops-mcp/blob/9a81b90b67623ebc68c25b281d7fbf4f6e791eb0/docs/TOOLSET.md). Isso comprova documentação do código local, não habilitação de ferramentas na organização do usuário nem paridade com o remoto.

Exemplos documentados nessa revisão:

| Necessidade | Ferramenta / ação documentada | Validação ainda necessária |
|---|---|---|
| Iterações e configuração | `work`: `list_iterations`, `list_team_iterations`, `get_team_settings` | Campos, escopo e paginação |
| Capacidade | `work`: `get_team_capacity`, `get_iteration_capacities` | Folgas, unidade, atividades e cobertura de times |
| Itens e tipos | `wit_work_item`: `get`, `get_batch`, `list_for_iteration`, `get_type` | Campos customizados e relações |
| Revisões | `wit_work_item`: `list_revisions` | Eventos, cortes, paginação e universo de itens |
| Consultas | `wit_query`: `get_results`, `wiql` | Schema, limites e semântica histórica |

Esses nomes não serão assumidos como constantes universais. Registrar catálogo e schemas retornados pela conexão, mapear operação lógica → ferramenta/ação compatível e falhar de forma explicativa quando a versão mudar.

O catálogo consultado não é prova de acesso genérico a Analytics/OData. Não anunciar esse acesso. Revisões de itens conhecidos também não provam descoberta completa de itens movidos ou excluídos. Sem cobertura verificável, histórico e baseline são parciais/indisponíveis. Snapshots locais começam na primeira coleta; não fabricam o passado.

## Segurança e auditabilidade

- Allowlist por ferramenta **e ação**. Por exemplo, ferramenta que lista backlog pode também permitir reordenação: permitir listagem não autoriza reordenação.
- Servidor oficial e organização devem ser configurados explicitamente; não aceitar endpoint arbitrário vindo de work item ou resposta do LLM.
- Autenticação é a suportada pelo MCP oficial conectado. O produto não recebe PAT/Entra para abrir um segundo acesso ao ADO.
- Sessões, tokens e segredos não entram em prompts, YAML compartilhado, logs ou relatórios.
- Registrar ferramenta/ação, argumentos sanitizados, horário, versão/catálogo, paginação, cobertura e hash de evidência. Um total é auditável até as respostas MCP usadas.
- Erro de autenticação, permissão, limite ou schema gera diagnóstico; retentativas limitadas nunca mudam o canal de acesso.
- Automação só é anunciada após validar modo MCP não interativo oficialmente suportado. Se faltar, manter renderização/replay offline e indicar que coleta agendada está indisponível.

## Aceite e efeito no roadmap

T03/T04 validam a cobertura antes de fechar a estimativa de implementação. T17 habilita apenas métricas históricas demonstradas. T23 valida coleta não interativa. T28 não contorna restrições do MCP para atender ao GPT.

V33 deve bloquear ferramenta inexistente, schema incompatível, escrita em ferramenta mista e qualquer tentativa de fallback direto. Testes de transporte permitem somente o canal MCP oficial e os endpoints de autenticação necessários à sessão; biblioteca HTTP transitiva do SDK MCP não configura, por si, acesso direto ao ADO. Registrar chamadas de domínio do cliente e impedir endpoints ADO REST/OData no produto. Testar replay com rede desabilitada.

Compatibilidade e análises permanecem **planejadas** até teste no servidor/host real. Nenhuma lacuna será escondida por coleta alternativa.
