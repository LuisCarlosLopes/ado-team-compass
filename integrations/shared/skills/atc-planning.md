---
name: atc-planning
description: Lista achados das regras de planejamento habilitadas para a equipe no Azure DevOps, com política, evidência e ação sugerida. Use para perguntas como "o que está inconsistente no board", "há prazos vencidos" ou "revisar higiene do backlog".
---

# Achados de planejamento

```
ado-team-compass planning --team <alias>
```

A saída traz apenas as regras habilitadas para o perfil da equipe. Regras desabilitadas não
produzem achado, e isso é intencional: story sem task, estimativa ausente e divergência de
área só aparecem quando a equipe declara essa política.

Ao apresentar:

- cite a regra, sua versão, a política e a ação sugerida;
- trate cada achado como ponto a confirmar, não como erro comprovado;
- não transforme quantidade de achados em score de saúde nem em percentual de confiança;
- não conclua produtividade ou esforço a partir de campos de trabalho registrado.
