# Runbook de operação da coleta agendada

Estado: procedimento entregável; a ativação da agenda é decisão de implantação. Nada aqui foi
executado em ambiente de produção real.

## O que a execução agendada faz

`ado-team-compass run-scheduled` coleta a situação atual pelo servidor MCP oficial, calcula,
persiste a execução e devolve um resumo com a chave de idempotência. A chave combina
configuração efetiva, equipe, janela e dia.

| Situação | Resultado | Código de saída |
|---|---|---|
| Primeira execução da chave | `executada` | 0, ou 5 se alguma capacidade ficou parcial |
| Reexecução da mesma chave | `ja_executada`, sem novo resultado | 0 |
| Execução simultânea da mesma chave | Erro `E_AGENDAMENTO_EM_ANDAMENTO` | 2 |
| Falha de autenticação ou permissão | `falha`; relatório anterior preservado | 3 |
| Falha de coleta sem relatório utilizável | `falha`; relatório anterior preservado | 4 |
| Schema incompatível | Erro de versão | 6 |

## Credencial expirada

Sintoma: saída 3 com `E_MCP_AUTENTICACAO`.

1. Renove a sessão do servidor MCP oficial conforme a orientação da Microsoft, no executor.
2. Rode `ado-team-compass doctor --non-interactive` e confirme `status: conectado`.
3. Reexecute o agendamento. O último relatório válido permanece disponível durante todo o
   incidente; nenhum relatório vazio o substitui.

Não configure PAT, token ou qualquer credencial de Azure DevOps no produto: ele não usa esse
caminho e não tem canal alternativo.

## Retentativa e limite de taxa

Erros de limite (`E_MCP_LIMITE`) e timeout (`E_MCP_TIMEOUT`) já são retentados dentro de um
orçamento de tempo, respeitando `Retry-After`. Se o orçamento se esgotar, reduza o escopo
(área, período ou lote) antes de aumentar a frequência da agenda. Não aumente a concorrência
acima do limite configurado.

## Lock preso

O lock vive em `<saída>/../schedule/locks/`. Se um processo morrer sem liberá-lo, ele é
reaproveitado automaticamente após duas horas. Para liberar antes disso, confirme que nenhuma
execução está rodando e remova o arquivo `.lock` correspondente.

## Retenção e purga

A retenção padrão é de 30 dias, configurável em `output.retention_days`. A purga remove
execuções cujo instante de referência é mais antigo que a janela. Execuções permanecem
imutáveis até serem removidas; não edite artefatos gravados.

## Artefato parcial

Uma execução com fontes parciais é marcada `partial` e traz os motivos no manifesto. Ela é um
resultado legítimo: publique-a com o rótulo de parcial, nunca como visão completa. Uma execução
interrompida antes do manifesto não é carregável e deixa um arquivo `INCOMPLETA.txt` com o
diagnóstico.

## Rollback

1. Reinstale a versão anterior do motor a partir do wheel da release correspondente.
2. Mantenha as execuções antigas: elas continuam legíveis enquanto a major do schema for a
   mesma.
3. Restaure o backup da configuração se a versão antiga não entender a configuração nova.
4. Nunca corrija um problema do relatório alterando work items no Azure DevOps.

## Notificações

A execução devolve um template de notificação apenas em mudança relevante de estado ou falha
acionável. Enviar exige canal configurado e autorização do operador — uma ação separada, fora
do escopo desta release.

## Aviso local opcional

O hook de sessão (`plugin/claude/hooks/`) apenas lê o manifesto local mais recente e avisa
quando ele está velho. Ele não coleta, não autentica e não faz nenhuma chamada de rede.
