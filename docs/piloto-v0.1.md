# Roteiro do piloto da v0.1

Estado: preparado, **não executado**. O piloto depende de acesso real a uma organização do
Azure DevOps e de equipes voluntárias; nada aqui declara resultado obtido.

## Pré-condições

- Sessão autenticada no servidor MCP oficial da Microsoft para a organização, com leitura das
  equipes selecionadas. O produto não recebe PAT nem token do Azure DevOps.
- Três equipes com práticas distintas: sprint com capacidade em horas, sprint sem horas e
  fluxo contínuo sem sprint.
- Uma pessoa responsável por equipe para revisar os achados.
- Para testar utilização global, disponibilidade pessoal informada explicitamente por escrito.

## Sequência

1. `demo` sem credencial, para validar instalação e formato.
2. `setup --organization <org>` e revisão dos perfis descobertos.
3. `doctor`: registrar versão do servidor, hash do catálogo e operações indisponíveis.
4. `status` por equipe e `render` do HTML.
5. Reconciliação: para cada equipe, revisar uma amostra fixa de 20 itens (ou todos, quando
   houver menos) e comparar os totais com uma consulta equivalente feita pela própria equipe
   no board.
6. `replay` da execução: confirmar `identical: true`.

## Registro obrigatório por equipe

| Campo | Conteúdo |
|---|---|
| Perfil e capacidades habilitadas | do arquivo de configuração efetiva |
| Operações MCP indisponíveis | saída do `doctor` |
| Divergências encontradas | item, total esperado, total apresentado e explicação |
| Falsos positivos | achado, por que não se aplica e regra correspondente |
| Decisões úteis | quais decisões o relatório tornou possíveis |

## Critérios de promoção

- Toda divergência numérica tem explicação; divergência sem explicação **bloqueia** a release.
- Nenhuma coleta parcial foi apresentada como visão completa.
- Nenhuma permissão de escrita foi solicitada em nenhum momento.
- Falsos positivos viram regra ou teste, nunca ajuste de texto escondido em instrução.
