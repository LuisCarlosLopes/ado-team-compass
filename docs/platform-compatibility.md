# Compatibilidade de plataformas — v1.4

Estado: bundles locais implementados; **nenhum host certificado em instalação real**.
Revisada em 13/09/2026. Inclui Claude Code, Antigravity, Codex, GPT personalizado no
ChatGPT e Cursor.

**Regra comum a todas as plataformas:** a comunicação com o Azure DevOps acontece
somente pelo [MCP oficial Microsoft](https://github.com/microsoft/azure-devops-mcp).
Não existe fallback REST/OData/SDK/CLI direto. [Contrato de acesso](ado-mcp-contract.md).

## Veredito

O ADO Team Compass **já foi desenhado para ser plugin**, mas o plugin **não é o motor**.
O motor é o pacote Python `ado-team-compass` (CLI `ado-team-compass`). Os hosts de IA
recebem um bundle de **skills** que mandam o assistente executar essa CLI. Este
repositório é **cliente MCP**, não servidor.

```text
Assistente (skill ou Action)
  → CLI local ou gateway HTTPS
    → motor Python
      → MCP oficial Azure DevOps
        → Azure DevOps
```

| Host | Formato oficial | Bundle no repo | Cabe como plugin? | Certificado |
|---|---|---|---|---|
| Claude Code | `.claude-plugin/plugin.json` + marketplace | [`plugin/claude/`](../plugin/claude/) + [`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json) | Sim — layout alinhado | Não |
| Google Antigravity IDE | `plugin.json` na raiz + `skills/` | [`plugin/antigravity/`](../plugin/antigravity/) | Sim — manifesto mínimo CLI-safe | Não |
| Codex local | `.codex-plugin/plugin.json` + `skills/` | [`plugin/codex/`](../plugin/codex/) | Sim como plugin local | Não |
| GPT personalizado no ChatGPT | Custom GPT + Actions (OpenAPI + OAuth) | [`integrations/chatgpt/`](../integrations/chatgpt/) | Parcial: contrato existe, infra não | Não |
| Cursor | `.cursor-plugin/plugin.json` + `skills/` | [`plugin/cursor/`](../plugin/cursor/) | Sim — layout Cursor Plugin | Não |

GPT é uma família de modelos, não um formato de plugin. O plano cobre uso no **Codex**
(plugin local) e **GPT personalizado no ChatGPT** (Actions remotas). Não fixar modelo no
núcleo e não exigir chave OpenAI adicional para executar o motor local.

## Como o plugin funciona

Fonte única: [`integrations/shared/`](../integrations/shared/) (skills +
[`hosts.yaml`](../integrations/shared/hosts.yaml)). O gerador
[`packaging/build_bundles.py`](../packaging/build_bundles.py) copia as oito skills
(`atc-setup`, `atc-doctor`, `atc-demo`, `atc-status`, `atc-allocation`, `atc-evidence`, `atc-history`,
`atc-planning`) para cada host, com rodapé de ambiente.

Padrão de invocação (skills locais): a skill chama uma ferramenta do servidor MCP do motor,
que acompanha o bundle — por exemplo `atc_status` com `team` e `format`. Não há comando de
shell na instrução.

Pré-requisitos em qualquer IDE local:

1. Python 3.11+ no sistema. O motor acompanha o bundle e é preparado na primeira execução por
   `bin/atc-mcp.py`; uma instalação existente de `ado-team-compass` é reaproveitada.
2. Servidor MCP oficial autenticado **no host** (não dentro do Compass).
3. Config local `.ado-team-compass/config.yaml`, gerada por `atc_setup` (pode reutilizar MCP
   do host com `from_mcp_config`).

Sem o item 2, só funcionam `atc_demo`, `atc_replay`, `atc_report`, `atc_render` e
`atc_evidence` sobre execuções já coletadas.

## Claude Code — compatível

Formato oficial: manifesto em `.claude-plugin/plugin.json`, skills em
`skills/<nome>/SKILL.md`, marketplace no repositório em `.claude-plugin/marketplace.json`.

O que o repositório já tem alinha com a documentação atual
([Create plugins](https://code.claude.com/docs/en/plugins)):

- Marketplace aponta `source: ./plugin/claude`.
- Skills com frontmatter `name` + `description` (descoberta automática).
- Hook opcional em [`plugin/claude/hooks/`](../plugin/claude/hooks/) (`SessionStart`, só
  metadados locais).

Riscos menores:

- O manifesto gerado inclui `requirements` (engine/version). Esse campo **não** faz parte
  do schema oficial do Claude; tende a ser ignorado e **não** instala o wheel.
- Nenhuma instalação real foi registrada. Publicar no marketplace comunitário é passo
  separado; o README ainda trata o bundle como artefato de Release.
- Licença privada no README pode impedir submissão a marketplaces públicos.

## Antigravity — compatível no IDE e CLI-safe

Formato oficial do IDE ([Plugins](https://antigravity.google/docs/ide/plugins/)):
diretório com `plugin.json` na raiz + `skills/<nome>/SKILL.md`. O bundle em
[`plugin/antigravity/`](../plugin/antigravity/) segue isso.

O schema do **CLI** Antigravity é estrito: aceita apenas `name` e `description` com
`additionalProperties: false`. Por isso, o gerador emite para o Antigravity um **manifesto mínimo**
(DECISÃO-002), sem `requirements`, `author`, `keywords` ou `skills`. O IDE descobre as skills
pela convenção da pasta `skills/`, tornando o bundle seguro tanto no IDE quanto no CLI.

Não há `mcp_config.json` no bundle — correto: a credencial ADO não deve ir no plugin. O
usuário configura o MCP oficial no próprio Antigravity.

O selo do IDE **não** vale por inferência para CLI/SDK.


## GPT — duas superfícies diferentes

### 1. Codex / plugin OpenAI local (já empacotado)

Formato oficial: `.codex-plugin/plugin.json` e `"skills": "./skills/"` (ou lista de
caminhos que começam com `./`). O bundle em [`plugin/codex/`](../plugin/codex/) usa lista
de pastas — aceitável.

Campos extras (`requirements`, `author`) não estão no contrato oficial; o deserializador
do Codex ignora desconhecidos. Falta `.mcp.json` / `.app.json` de propósito: o MCP oficial
é configurado no host, não embutido.

Não anunciar a extensão IDE do Codex com base neste bundle. A documentação OpenAI
distingue CLI/desktop de extensão IDE.

### 2. GPT personalizado no ChatGPT (não é plugin local)

ChatGPT **não executa CLI na máquina**. A integração prevista é Custom GPT + Actions:

- Contrato: [`integrations/chatgpt/openapi.json`](../integrations/chatgpt/openapi.json)
  (OpenAPI 3.1, só GET).
- Instruções: [`integrations/chatgpt/instrucoes-gpt.md`](../integrations/chatgpt/instrucoes-gpt.md).
- Código: gateway FastAPI no extra `api` (`src/ado_team_compass/gateway/`).

Estado: schema e app existem; **nenhuma infra foi publicada**. Para funcionar de verdade
faltam domínio HTTPS, OAuth corporativo, ACL de equipes, coletor agendado (MCP oficial não
interativo) e um GPT que importe o OpenAPI. Planejado para v0.3.1, não v0.1.

O token do GPT autoriza só a API de relatórios. Não há canal ADO direto a partir do
ChatGPT. Ausência retorna 404; dados antigos retornam com aviso. Atualizar o GPT não
atualiza o coletor.

Domínio HTTPS acessível pelo ChatGPT, identidade, política de dados e plano/workspace com
Actions habilitado são requisitos de implantação. Não publicar serviço anônimo, link de
relatório público ou GPT em catálogo automaticamente.

## Cursor — bundle implementado (Cursor Plugin)

Cursor em 2026 tem plugin de primeira classe
([Plugins reference](https://cursor.com/docs/reference/plugins)):

- **Cursor Plugin:** `.cursor-plugin/plugin.json` + skills, rules, commands, hooks,
  variables.
- **Agent Plugin:** `plugin.json` na raiz + `skills/` + `mcp.json` (padrão aberto alternativo).

Implementação no repositório:

- Entrada `cursor` em [`integrations/shared/hosts.yaml`](../integrations/shared/hosts.yaml).
- Bundle gerado em [`plugin/cursor/`](../plugin/cursor/) com manifesto em `.cursor-plugin/plugin.json`,
  as oito skills compartilhadas e README de instalação (DECISÃO-001).
- Inclusão automática no pacote de release zip (`ado-team-compass-cursor-<versão>.zip`).
- A CLI aceita `--from-mcp-config` apontando para `.cursor/mcp.json` ou variáveis de ambiente.
- Setup grava referência de ambiente para reutilizar a sessão MCP do Cursor sem copiar segredo.
- **Zero segredos:** nenhum `mcp.json` com PAT é embutido no bundle. O usuário configura o servidor MCP
  oficial no Cursor.

Estado: **implementado**, porém **não verificado em instalação real** (permanece como "planejado"
na [matriz de certificação](host-certification-matrix.md)).

## Riscos de schema nos manifests

Os bundles locais são gerados a partir da fonte comum, com especialização por host no gerador.

| Campo gerado | Claude | Codex | Antigravity CLI | Cursor |
|---|---|---|---|---|
| `requirements` (engine/version) | Extra — costuma ignorar | Extra — costuma ignorar | Omitido (CLI-safe) | Extra — costuma ignorar |
| `author` / `keywords` / `skills[]` | OK / tolerado | `skills` como lista `./…` OK | Omitido (CLI-safe) | OK / tolerado |
| Instala o wheel Python? | Não | Não | Não | Não |

O campo `requirements` **não** faz parte do schema oficial de nenhum host e **não**
substitui a instalação do pacote Python.

## Riscos comuns

- **Nada foi testado no host real.** Status permitido na matriz de validação: planejado,
  testado, falhou ou não suportado. Hoje tudo permanece “implementado / não verificado”.
- O bundle carrega o motor e o prepara sozinho, mas **depende de Python 3.11+ no sistema**:
  uma dependência do motor tem código compilado. Onde o `python3` do sistema é anterior a
  3.11, o launcher procura um interpretador compatível no PATH e falha com mensagem acionável
  se não houver nenhum.
- A preparação automática **exige rede na primeira execução** para resolver as dependências do
  wheel. Em ambiente fechado, instale o motor antes e use `ADO_TEAM_COMPASS_NO_BOOTSTRAP=1`.
- Só o Claude Code sobe o servidor sem registro manual; nos demais hosts a entrada de
  `mcp-server.json` precisa ser copiada com o caminho absoluto do bundle.
- Licença privada + repositório privado limitam publicação em marketplace (Cursor, Claude
  community, OpenAI plugin store).
- Arquivos `mcp.json` locais estão no `.gitignore` — correto, porque costumam carregar PAT.

## Matriz de validação obrigatória

Registrar para cada combinação: versão do host, sistema operacional, versão do
motor/schema, instalação, descoberta de skill, relatório, evidência, atualização e
desinstalação.

- Motor: Windows, macOS e Linux.
- Claude Code: combinações suportadas e selecionadas para a release.
- Antigravity: IDE em combinações suportadas; CLI/SDK não recebem selo por inferência.
- Codex: CLI e superfície desktop suportada. Não anunciar extensão IDE com base nesses
  testes.
- GPT personalizado: Actions em conta/workspace de teste autorizado; não generalizar para
  todos os planos.
- Cursor: quando existir bundle, validar Agent Plugin e/ou Cursor Plugin em instalação
  real; atalho via `.cursor/skills/` não conta como certificação de plugin.

Usar fixture idêntica nos hosts locais e na API. Comparar JSON de métricas, referências e
limitações; prosa pode variar. Incluir dados incompletos, credencial expirada, caminhos com
espaços, versão incompatível e desinstalação de um bundle mantendo outros.

O suporte só passa a “testado” após evidência no host real. A publicação deste documento
não implementa nem certifica compatibilidade.

A API HTTPS entre GPT e gateway consulta relatórios existentes e não é um canal alternativo
para o ADO. Qualquer nova coleta, em qualquer host, exige o MCP oficial.

## Estado da implementação — 13/09/2026

Os quatro bundles locais são gerados de uma fonte comum (`integrations/shared/`) e
empacotados com o wheel do motor e o lock da release. O gateway para GPT personalizado
existe como código, OpenAPI e instruções (fora do escopo local; v0.3.1).

| Ambiente | Implementado | Verificado em host real |
|---|---|---|
| Claude Code | Manifesto, skills e hook opcional | Não (planejado) |
| Google Antigravity | Manifesto mínimo na raiz e skills | Não (planejado) |
| Codex | Manifesto `.codex-plugin` e skills | Não (planejado) |
| Cursor | Manifesto `.cursor-plugin`, skills e README | Não (planejado) |
| GPT personalizado | API autenticada, OpenAPI e instruções | Não (adiado v0.3.1) |

Paridade de métricas entre hosts é garantida por construção: as skills compartilham o corpo
das instruções e todos os números vêm do mesmo motor Python. Isso não substitui a
instalação e a execução reais, que continuam pendentes. A matriz de validação e o roteiro de
certificação manual encontram-se em
[`docs/host-certification-matrix.md`](host-certification-matrix.md).

## Recomendação

1. **Claude, Antigravity, Codex e Cursor:** bundles locais implementados e validados por
   testes de contrato e empacotamento. O próximo passo operacional é executar a certificação manual
   conforme a [matriz de certificação](host-certification-matrix.md).
2. **GPT:** tratar Codex (local, já empacotado) separado de ChatGPT Actions (remoto,
   depende de gateway). Não vender os dois como o mesmo plugin.
3. **Não** transformar o Compass em servidor MCP próprio: mudaria o contrato de segurança e
   duplicaria o que o MCP oficial já expõe.

