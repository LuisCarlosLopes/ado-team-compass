---
name: atc-allocation
description: Mostra carga conhecida por pessoa e capacidade restante de uma execução do ADO Team Compass. Use quando perguntarem quem está sobrecarregado, como redistribuir trabalho ou qual a carga de alguém.
---

# Carga conhecida por pessoa

Chame a ferramenta `atc_allocation` com `team`. Ela lê a execução persistida mais
recente: se não houver nenhuma, rode `atc_status` antes.

Apresente a tabela como ela vem: carga conhecida, capacidade restante reservada, utilização,
classe e quantos itens estão sem valor.

- Classe `DADOS_INSUFICIENTES` significa que faltam estimativas: não conclua carga baixa.
- Classe `SEM_CARGA_REGISTRADA` pede verificação com a pessoa; não é ociosidade e não autoriza
  redistribuir trabalho automaticamente.
- Reserva de capacidade em várias equipes não prova disponibilidade total da pessoa.
- Carga sem responsável aparece em linha própria e continua fazendo parte da carga da equipe.
- Transferência de trabalho é candidata: cite o efeito aritmético e o que confirmar
  (dependências, habilidades, prioridade). Nunca prometa prazo ou produtividade.
