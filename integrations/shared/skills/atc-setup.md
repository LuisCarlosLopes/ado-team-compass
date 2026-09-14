---
name: atc-setup
description: Configura o ADO Team Compass para uma organização do Azure DevOps, descobrindo projetos e equipes pelo MCP oficial. Use quando pedirem para configurar, instalar ou conectar o compass a uma organização.
---

# Configurar o ADO Team Compass

O Compass **não herda a sessão de MCP do host**: ele abre a própria conexão com o servidor
oficial da Microsoft, a partir de `.ado-team-compass/config.yaml`. Ter o servidor oficial
configurado no host não basta — o setup precisa acontecer.

Prefira reaproveitar a definição que o host já tem: chame `atc_setup` com `from_mcp_config`
apontando para o arquivo de configuração de MCP do host (e `mcp_server`, se o servidor não se
chamar `ado`). Isso copia comando e argumentos e deixa apenas uma referência ao arquivo de
onde o ambiente é lido na conexão — nenhuma credencial entra na configuração do Compass.

Sem essa configuração no host, peça a organização e chame `atc_setup` com `organization`. Esse
caminho usa o servidor remoto oficial e exige uma autorização explícita: se `atc_doctor`
responder `exit_code` 3, chame `atc_login` antes de coletar.

Depois do setup:

1. Revise o perfil de cada equipe (`sprint_with_capacity`, `sprint_without_hours` ou
   `continuous_flow`). O processo técnico descoberto não define a prática de gestão.
2. Preencha o que o MCP não expôs — áreas, inclusão de descendentes, mapeamento de estados —
   em vez de assumir valores.
3. Chame `atc_doctor` e mostre as operações indisponíveis com o motivo.

Se o setup terminar com `exit_code` 5, a configuração foi gravada mas há limitações: liste-as.
