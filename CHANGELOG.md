# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Versionamento semântico do motor; os contratos têm versão de schema própria (`schema_version`).

## [Não lançado]

## [0.3.0] — 2026-09-14

### Alterado

- O motor passa a ser servido ao assistente como **servidor MCP local** (`ado-team-compass-mcp`):
  as skills chamam ferramentas `atc_*` em vez de comandos de shell. Cada ferramenta é um
  envelope sobre a mesma entrada da CLI, com os mesmos cálculos e os mesmos códigos de saída.
- Instalar o plugin deixou de exigir instalar a CLI antes. Todo bundle traz `bin/atc-mcp.py`,
  um launcher só com biblioteca padrão que reaproveita um motor já instalado ou prepara o
  wheel embutido em um ambiente isolado sob `~/.ado-team-compass/runtime`, uma única vez.
- O manifesto do Claude Code declara o servidor e o sobe junto com o plugin. Antigravity,
  Codex e Cursor não expõem a raiz do bundle, então recebem um `mcp-server.json` pronto para
  registrar à mão.
- O campo `requirements` saiu dos manifestos: o motor não é mais pré-requisito externo.
- O transporte remoto oficial passa a **autorizar de verdade**. Antes, a conexão HTTP era
  aberta sem credencial nenhuma e só podia falhar com 401. Agora há o fluxo OAuth do SDK MCP
  (descoberta, registro dinâmico, PKCE e renovação), exposto pelas entradas `login` e `logout`
  e pelas ferramentas `atc_login` e `atc_logout`. Nenhuma senha, PAT ou token é pedido pelo
  produto: quem autentica é o provedor de identidade da organização, no navegador.
- Coleta nunca abre navegador nem espera por pessoa: sem autorização válida, a resposta é
  saída 3 com a orientação de chamar `login`. O material de autorização vive isolado em
  `~/.ado-team-compass/auth`, com permissão restrita ao dono, e nunca entra na configuração,
  nos artefatos de execução ou em log. `doctor` passa a relatar o estado, sem expor valores.
- Documentação corrigida: o Compass **não herda a sessão de MCP do host**. Ele abre a própria
  conexão a partir de `.ado-team-compass/config.yaml`, e `--from-mcp-config` copia apenas a
  definição do servidor mais uma referência ao arquivo de onde o ambiente é lido.
- Requisito mínimo de Python baixou de 3.12 para **3.11**. Nenhuma dependência exigia 3.12
  (o piso real era 3.10, de `mcp` e `anyio`) e o código não usa sintaxe nem API exclusivas
  de 3.12. A suíte completa roda em 3.11, que entrou na matriz do CI.

### Corrigido

- A matriz do CI passa a usar de fato `matrix.python-version` no setup do uv e confirma o
  interpretador em uso. O teste de permissão do material de autorização deixa de assumir
  modo POSIX, para o job Windows não falhar.

## [Não lançado] — v0.1 em construção

### Adicionado

- Pacote Python `ado-team-compass` com CLI, códigos de saída estáveis e erros acionáveis (T01).
- Contratos versionados de configuração, fatos, métricas, resumo, manifesto, narrativa e
  decisões; resolução de configuração por precedência com proveniência por chave (T02).
- Cliente do MCP oficial da Microsoft com servidor remoto como canal padrão, negociação de
  catálogo, allowlist por ferramenta e ação, retentativa com orçamento e registro auditável (T03).
- Descoberta de projetos e equipes e geração de configuração sem segredos (T04).
- Coleta e normalização da situação atual com cobertura e motivos explícitos (T05).
- Execuções imutáveis com escrita atômica, evidência minimizada, cache isolado e retenção (T06).
- Métricas de qualidade, calendário/capacidade, carga, classes e consolidação entre equipes
  (T07 a T10).
- Relatório determinístico em Markdown, resumo limitado e replay reproduzível (T11).
- Validação da interpretação do modelo de linguagem contra a execução (T12).
- Relatório HTML operacional offline com candidatos de ação e registro de decisões (T22).
- Bundles para Claude Code, Antigravity e Codex gerados de uma fonte comum (T13, T26, T27).
- Validação transversal de desempenho, segredos, retenção e schema; empacotamento da release
  candidata com motor embutido (T14, T15).

- Histórico por revisões do MCP, compromisso, mudança de escopo, carry-over, throughput,
  cycle/lead time, aging e percentis; regras de planejamento por perfil (T17 a T21).
- Execução agendada idempotente com lock, runbook e templates de pipeline (T23, T24).
- Gateway HTTPS autenticado de leitura com OpenAPI e instruções para GPT Actions (T28).
- Forecast experimental com premissas, semente e backtesting publicado (T25).

### Limites desta versão

- Somente leitura do Azure DevOps, exclusivamente pelo MCP oficial da Microsoft.
- Nenhuma conexão real com o Azure DevOps foi executada: os nomes de ferramenta do catálogo
  MCP e os formatos de resposta permanecem não verificados até o primeiro handshake.
- Instalação nos hosts em perfil limpo, piloto com equipes reais e implantação do gateway
  continuam pendentes.
- O forecast permanece experimental até ser calibrado com histórico real.
