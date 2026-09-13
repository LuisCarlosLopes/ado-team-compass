---
name: ado-compass-doctor
description: Diagnostica ambiente, configuração, sessão MCP e operações disponíveis do ADO Team Compass. Use quando algo falhar, quando perguntarem se a conexão está funcionando ou antes da primeira coleta.
---

# Diagnosticar o ADO Team Compass

```
ado-team-compass doctor
```

Reporte, nesta ordem: versão do motor, validade da configuração, canal e versão do servidor
MCP, hash do catálogo, operações resolvidas e operações indisponíveis com o motivo.

- Saída 3 significa autenticação ou permissão: peça para autenticar a sessão do servidor MCP
  oficial conforme a orientação da Microsoft. Não sugira PAT no produto nem outro canal.
- Saída 5 significa que faltam operações no catálogo conectado: diga quais análises ficam
  indisponíveis em vez de prometer o relatório completo.
- Com `--offline`, o diagnóstico valida ambiente e configuração e declara a coleta indisponível.
