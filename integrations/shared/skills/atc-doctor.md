---
name: atc-doctor
description: Diagnostica ambiente, configuração, sessão MCP e operações disponíveis do ADO Team Compass. Use quando algo falhar, quando perguntarem se a conexão está funcionando ou antes da primeira coleta.
---

# Diagnosticar o ADO Team Compass

Chame a ferramenta `atc_doctor`.

Reporte, nesta ordem: versão do motor, validade da configuração, canal e versão do servidor
MCP, estado da autorização, hash do catálogo, operações resolvidas e operações
indisponíveis com o motivo.

- `exit_code` 3 significa autenticação ou permissão. O relatório traz o bloco `authorization`:
  se ele disser que não há autorização local, chame `atc_login` — o usuário autoriza no
  navegador e nenhuma senha, PAT ou token passa pelo Compass. Se a conexão for stdio, a
  credencial pertence ao ambiente do host: peça para reautenticar lá, conforme a orientação da
  Microsoft. Não sugira PAT no produto nem outro canal.
- Saída 5 significa que faltam operações no catálogo conectado: diga quais análises ficam
  indisponíveis em vez de prometer o relatório completo.
- Com `offline: true`, o diagnóstico valida ambiente e configuração e declara a coleta
indisponível.
