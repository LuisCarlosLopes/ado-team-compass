# Automação da coleta

Os arquivos deste diretório são **templates**. Copiá-los não ativa nada: agendamento, canal de
notificação e destino dos artefatos são decisões de implantação.

## Pré-condições

- Uma sessão própria do servidor MCP oficial da Microsoft no executor. Sem ela, a coleta não
  roda: o produto não tem canal alternativo e não aceita PAT do Azure DevOps.
- Versão do motor fixada na instalação (`ado-team-compass==<versão>`).
- Configuração compartilhável versionada; dados pessoais ficam em `config.local.yaml`, que não
  é versionado.

## Garantias da entrada `run-scheduled`

| Situação | Comportamento |
|---|---|
| Reexecução no mesmo dia, mesma configuração, equipe e janela | `ja_executada`, sem duplicar resultado |
| Duas execuções simultâneas da mesma chave | A segunda termina com erro de lock, sem produzir um segundo resultado |
| Falha de coleta após um sucesso | O último relatório válido é preservado; nenhum relatório vazio o substitui |
| Mudança de configuração, equipe, janela ou dia | Nova chave, nova execução |

## Notificações

A execução devolve um **template** de notificação apenas quando há mudança relevante de estado
ou falha acionável. Nada é enviado: publicar exige canal configurado e autorização do operador,
e isso é uma ação futura separada.

## Publicação

O template publica as execuções como artefato privado do pipeline escolhido. Não há promessa de
URL pública estável, e o relatório pode conter nomes e dados internos: trate o artefato como
material restrito.
