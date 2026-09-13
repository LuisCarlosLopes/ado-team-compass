---
name: atc-history
description: Mostra compromisso, mudança de escopo, say/do, carry-over e métricas de fluxo de uma equipe no Azure DevOps. Use para perguntas como "quanto do que planejamos foi entregue", "o escopo mudou", "qual nosso cycle time" ou "o time está melhorando".
---

# Histórico e compromisso

```
ado-team-compass history --team <alias> --format markdown
```

Antes de interpretar, confira o bloco histórico:

- Se a baseline for **técnica**, diga isso: sem corte de compromisso configurado, o início da
  sprint é apenas uma referência e não prova compromisso confirmado.
- Say/do conta apenas itens da baseline; itens adicionados depois não entram no numerador.
- Entradas e saídas de escopo são números separados. Nunca apresente só o saldo líquido, e
  destaque itens que entraram e saíram na mesma janela.
- Carry-over da baseline não é o mesmo que trabalho movido para a próxima sprint.
- Percentis usam nearest-rank em dias corridos. Com amostra pequena, diga que são indicativos.
- Períodos sem entrega continuam na série com zero: não os omita.
- Variação entre janelas é descrição, não prova de melhora ou piora. Não compare pontos entre
  equipes e não trate histórico de trabalho registrado como timesheet.

Se a saída for 5 com histórico indisponível, informe o motivo do relatório: a ferramenta de
revisões pode não existir no catálogo conectado ou a cobertura pode ser insuficiente.
