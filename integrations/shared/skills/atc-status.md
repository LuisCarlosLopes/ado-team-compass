---
name: atc-status
description: Coleta e apresenta a situação atual de uma equipe no Azure DevOps — itens abertos, carga conhecida, capacidade restante, gap e impedimentos. Use para perguntas como "como está a sprint", "o time está sobrecarregado", "o que precisa de atenção hoje" ou "resumo da daily".
---

# Situação atual da equipe

Chame a ferramenta `atc_status` com `team` (alias da equipe) e `format`
(`markdown` para leitura, `json` para inspecionar campo a campo).

Sem equipe informada e com mais de uma configurada, a execução falha com saída 2: pergunte
qual equipe em vez de escolher a primeira.

Ao responder, use exatamente os números do relatório e diga, para cada um:

- o valor com a unidade (horas, pontos ou itens: nunca converta entre elas);
- o status da métrica e a cobertura de itens;
- o motivo, quando a métrica for parcial, indisponível ou não aplicável.

Para o resumo de daily, priorize: gap de capacidade conhecido, impedimentos registrados, itens
abertos sem estimativa e até três ações candidatas com o que precisa ser confirmado antes de
decidir. Utilização parcial não sustenta afirmação de carga baixa; sobrecarga demonstrada pela
carga conhecida pode ser citada como limite inferior.

Para gerar o relatório navegável offline, chame `atc_render`: ela devolve o caminho
do HTML autocontido gravado localmente.
