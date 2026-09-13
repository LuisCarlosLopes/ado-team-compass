---
name: atc-evidence
description: Recupera a evidência local de uma execução do ADO Team Compass e reprocessa métricas congeladas. Use quando pedirem para explicar de onde vem um número, auditar um total ou repetir um cálculo anterior.
---

# Explicar um número com evidência

Para listar os artefatos e conferir integridade:

```
ado-team-compass evidence --team <alias>
```

Para abrir a evidência de um item:

```
ado-team-compass evidence --reference <id-do-item>
```

Para recalcular com as entradas congeladas:

```
ado-team-compass replay --team <alias>
```

O replay deve devolver `identical: true`. Se devolver `false`, houve mudança de versão ou de
configuração: relate isso em vez de apresentar o novo número como se fosse o anterior. Hash de
artefato prova integridade, não autenticidade. A evidência guarda excerto de título, nunca a
descrição integral, e nenhuma credencial.
