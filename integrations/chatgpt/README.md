# GPT personalizado com Actions

Estado: contrato e schema entregues; **nenhuma infraestrutura foi criada ou publicada**.

## Como montar

1. Implante o gateway em um domínio HTTPS alcançável pelo ChatGPT, dedicado à organização.
2. Configure o provedor OAuth corporativo (authorization code) e a ACL de equipes do servidor.
3. No GPT personalizado, importe `openapi.json` como Action e configure a autenticação OAuth.
4. Cole `instrucoes-gpt.md` nas instruções do GPT.

## Fronteiras

- O token do GPT autoriza somente esta API. Ele não dá acesso ao Azure DevOps.
- O coletor que produz os relatórios usa exclusivamente o servidor MCP oficial da Microsoft e
  roda separadamente desta API.
- Todas as rotas são GET. Não há execução de comando, WIQL livre, URL arbitrária ou escrita.
- Disponibilidade de Actions depende do plano e das políticas do workspace do usuário; isso só
  pode ser confirmado no teste de integração real.

Regenerar o schema: `python -c "from pathlib import Path; from ado_team_compass.gateway.schema import export_openapi; export_openapi(Path('integrations/chatgpt/openapi.json'))"`
