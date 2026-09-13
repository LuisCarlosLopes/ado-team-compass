# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Versionamento semântico do motor; os contratos têm versão de schema própria (`schema_version`).

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

### Limites desta versão

- Somente leitura do Azure DevOps, exclusivamente pelo MCP oficial da Microsoft.
- Histórico, baseline, fluxo, planejamento, execução agendada, API para GPT e forecast não
  entram na v0.1.
- Compatibilidade com cada host e cobertura real do catálogo MCP continuam a validar em
  instalação e organização reais (T16).
