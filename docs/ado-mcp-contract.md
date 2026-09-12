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

## Catálogo verificado e limites

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
