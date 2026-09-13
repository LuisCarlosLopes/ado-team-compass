---
name: ado-compass-setup
description: Configura o ADO Team Compass para uma organização do Azure DevOps, descobrindo projetos e equipes pelo MCP oficial. Use quando pedirem para configurar, instalar ou conectar o compass a uma organização.
---

# Configurar o ADO Team Compass

Peça a organização do Azure DevOps se ela não foi informada. Em seguida execute:

```
ado-team-compass setup --organization <organizacao>
```

A descoberta grava `.ado-team-compass/config.yaml` sem nenhuma credencial: a sessão do Azure
DevOps pertence ao servidor MCP oficial. Depois do setup:

1. Revise o perfil de cada equipe (`sprint_with_capacity`, `sprint_without_hours` ou
   `continuous_flow`). O processo técnico descoberto não define a prática de gestão.
2. Preencha o que o MCP não expôs — áreas, inclusão de descendentes, mapeamento de estados —
   em vez de assumir valores.
3. Rode `ado-team-compass doctor` e mostre as operações indisponíveis com o motivo.

Se o setup terminar com saída 5, a configuração foi gravada mas há limitações: liste-as.
