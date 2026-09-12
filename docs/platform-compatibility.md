# Compatibilidade de plataformas — v1.3

Estado: especificação planejada, sem integração implementada ou certificada. Revisada em 12/09/2026. O pedido inclui Antigravity e GPT, preservando Claude Code.

**Regra comum a todas as plataformas:** a comunicação com o Azure DevOps acontece somente pelo [MCP oficial Microsoft](https://github.com/microsoft/azure-devops-mcp). Não existe fallback REST/OData/SDK/CLI direto. [Contrato de acesso](ado-mcp-contract.md).

## Superfícies e entregas

| Host | Pacote proposto | Execução | Entrega |
|---|---|---|---|
| Claude Code | `plugin/claude/`, manifesto Claude e skills | Cliente MCP oficial + motor local | v0.1, T13 |
| Antigravity IDE | `plugin/antigravity/`, `plugin.json` e skills | Cliente MCP oficial + motor local | v0.1, T26 |
| Codex local | `plugin/codex/`, `.codex-plugin/plugin.json` e skills | Cliente MCP oficial + motor local em superfície suportada | v0.1, T27 |
| GPT personalizado no ChatGPT | `integrations/chatgpt/`, OpenAPI e instruções | API HTTPS de leitura de relatórios | v0.3.1, T28 |

GPT é uma família de modelos, não um formato de plugin. O plano cobre uso no Codex e GPT personalizado; um aplicativo próprio que chama modelos por API é outro produto. Não fixar modelo no núcleo e não exigir chave OpenAI adicional para executar o motor local.

## Fonte comum e diferenças dos hosts

Instruções, exemplos e referências ficam em `integrations/shared/`. O processo de empacotamento gera cópias autocontidas para cada host, com hash de origem. Manifestos, sintaxe de ferramentas, localização dos executáveis, instalação e hooks são adaptados. Não usar links para arquivos fora do bundle instalado nem alterar fórmulas entre versões do mesmo motor.

Antigravity documenta plugins com `plugin.json` na raiz e skills. Também admite skills no workspace em `.agents/skills/`. Usar o pacote nativo como principal e instalação de skills como alternativa; não presumir compatibilidade de recursos entre IDE, CLI e SDK. [Plugins Antigravity](https://www.antigravity.google/docs/plugins), [Skills Antigravity](https://antigravity.google/docs/skills).

Codex deve usar seu pacote próprio, verificando a versão do host na implementação. A documentação distingue superfícies que suportam plugins, incluindo CLI e desktop, da extensão IDE. Instalação na web não significa que scripts locais foram implantados. [Plugins OpenAI](https://learn.chatgpt.com/docs/plugins), [Skills OpenAI](https://learn.chatgpt.com/docs/build-skills).

## GPT personalizado: contrato remoto

O GPT usa Actions para consultar uma API; não recebe acesso implícito à máquina do usuário. [GPT Actions](https://developers.openai.com/api/docs/actions/introduction).

Operações propostas, documentadas em OpenAPI na implementação:

| Operação | Retorno | Restrição |
|---|---|---|
| Listar equipes permitidas | IDs e nomes visíveis ao usuário | ACL aplicada no servidor |
| Consultar último relatório da equipe | Métricas, recomendações, timestamp, run ID e limitações | Sem recomputar ou disparar job longo |
| Consultar evidência da execução | Dados sanitizados paginados | Autorização por equipe e execução em cada chamada |

O coletor agendado produz os relatórios usando exclusivamente ferramentas do MCP oficial. Seu modo de autenticação não interativo deve ser oficialmente suportado e testado; sem isso, a coleta agendada fica indisponível. O gateway usa o mesmo contrato da CLI, com uma implantação dedicada por organização. API somente de leitura, sem consulta livre, shell, proxy HTTP ou alteração no ADO. Ausência retorna 404; dados antigos retornam com aviso. Atualizar ou instalar um GPT não atualiza automaticamente o coletor.

OAuth por usuário foi escolhido porque a integração contém dados internos com acesso por equipe; Actions oferece esse modo de autenticação. A autenticação ADO é tratada pela conexão com o MCP oficial; não há token ADO direto no coletor. O token do GPT autoriza somente a leitura da API de relatórios. O serviço valida emissor/audiência, revogação e ACL, nega por padrão e protege também links para HTML/evidências. [Autenticação de GPT Actions](https://developers.openai.com/api/docs/actions/authentication).

Domínio HTTPS acessível pelo ChatGPT, identidade, política de dados e plano/workspace com Actions habilitado são requisitos de implantação. Não publicar serviço anônimo, link de relatório público ou GPT em catálogo automaticamente. Compartilhamento de GPT, backend e repositório são operações distintas.

## Matriz de validação obrigatória

Registrar para cada combinação: versão do host, sistema operacional, versão do motor/schema, instalação, descoberta de skill, relatório, evidência, atualização e desinstalação. Status permitido: planejado, testado, falhou ou não suportado. Atualmente todas as integrações estão planejadas.

- Motor: Windows, macOS e Linux.
- Claude Code: combinações suportadas e selecionadas para a release, declaradas no relatório de testes.
- Antigravity: IDE em combinações suportadas; CLI/SDK não recebem selo por inferência.
- Codex: CLI e superfície desktop suportada. Não anunciar extensão IDE com base nesses testes.
- GPT personalizado: Actions em conta/workspace de teste autorizado; não generalizar aprovação para todos os planos.

Usar fixture idêntica nos três hosts locais e na API. Comparar JSON de métricas, referências e limitações; prosa pode variar. Incluir dados incompletos, credencial expirada, caminhos com espaços, versão incompatível e desinstalação de um bundle mantendo outros.

O suporte só passa a “testado” após evidência no host real. A publicação atual deste documento no GitHub não implementa nem certifica compatibilidade.

A API HTTPS entre GPT e gateway consulta relatórios existentes e não é um canal alternativo para o ADO. Qualquer nova coleta, em qualquer host, exige o MCP oficial; nenhuma limitação de Actions autoriza conexão ADO direta.
