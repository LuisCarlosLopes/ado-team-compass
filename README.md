# ADO Team Compass
> Transforme o board do Azure DevOps em um relatório de sprint claro, auditável e pronto para a daily — em segundos.

[![Última versão](https://img.shields.io/github/v/release/LuisCarlosLopes/ado-team-compass?display_name=tag&label=versão&color=0B5CAB)](https://github.com/LuisCarlosLopes/ado-team-compass/releases/latest)
[![Plataformas](https://img.shields.io/badge/plataformas-macOS%20%7C%20Linux%20%7C%20Windows-informational)](#-instalação)
[![Licença](https://img.shields.io/badge/licença-Privada-lightgrey)](LICENSE)

<!-- [Screenshot / Demo GIF placeholder] -->

## ✨ O que é e por que usar?

Times que entregam no Azure DevOps perdem tempo montando a daily à mão: exportam planilhas, somam horas no Excel e ainda assim não sabem se o trabalho conhecido cabe na capacidade restante — nem o que está realmente bloqueado. O ADO Team Compass lê a situação da equipe e devolve um relatório objetivo: o que está aberto, o que está impedido, se a carga cabe na reserva e o que precisa de decisão hoje.

Foi desenhado para Scrum Masters, tech leads e gestores de entrega que precisam de uma leitura honesta do board, sem ranking individual e sem colar token do Azure DevOps na ferramenta. A autenticação fica na sessão oficial da Microsoft; você só pede o recorte da equipe e recebe o relatório.

## ⚡ Principais Recursos

- **Resposta pronta para a daily:** itens abertos, impedimentos e o que precisa de atenção hoje, em um único comando.
- **Carga versus capacidade:** compara o trabalho restante conhecido com a reserva da equipe e aponta sobrecarga ou folga — sem ranquear pessoas.
- **Relatório visual offline:** HTML autocontido para abrir no navegador, Markdown no terminal e JSON para arquivar.
- **Perfis de gestão reais:** sprint com horas, sprint sem horas e fluxo contínuo, sem forçar um modelo que o time não usa.
- **Números rastreáveis:** cada total aponta para a evidência local; dá para reabrir o mesmo recorte e conferir de onde veio o valor.
- **Modo demonstração:** experimente o relatório completo sem organização, senha ou rede.
- **Somente leitura:** nada é alterado no Azure DevOps. Sem PAT, token ou senha guardados no Compass.
- **Uso no assistente que você já tem:** bundles para Claude Code, Google Antigravity, OpenAI Codex e Cursor, com o motor embutido, para perguntar “como está a sprint?” em linguagem natural sem instalar nada antes.

## 📥 Instalação

Requisito: **Python 3.11 ou superior**, em macOS, Linux ou Windows.

### Pacote pronto (para uso no terminal)

1. Abra a [página de Releases](https://github.com/LuisCarlosLopes/ado-team-compass/releases/latest).
2. Baixe o arquivo `.whl` da versão mais recente.
3. Instale:

```bash
pip install ado_team_compass-*.whl
```

Confira com `ado-team-compass version`. Para ver o relatório sem conectar ao Azure DevOps:

```bash
ado-team-compass demo --format html --output relatorio-demo.html
```

Abra `relatorio-demo.html` no navegador.

### Assistentes de IA

Na mesma Release, baixe o bundle do host que você usa (**Claude Code**, **Google Antigravity**, **Codex** ou **Cursor**) e instale-o. **Não é preciso instalar a CLI antes:** o bundle traz o motor e o prepara sozinho na primeira execução, em um ambiente isolado sob `~/.ado-team-compass/runtime`. Se você já instalou o pacote acima, é essa instalação que o bundle usa.

O motor é servido ao assistente como um servidor MCP local: as skills chamam ferramentas (`atc_status`, `atc_demo`, `atc_doctor`…), não comandos de shell. Falta apenas apontar o assistente para o [servidor MCP oficial do Azure DevOps](https://github.com/microsoft/azure-devops-mcp) da sua organização — é por ele que toda leitura acontece. Depois disso, perguntas como “o que precisa de atenção na daily?” passam a usar o mesmo relatório.

Requisito do bundle: Python 3.11 ou superior no sistema. Para fixar um interpretador, aponte `ADO_TEAM_COMPASS_ENGINE_PYTHON` para ele.

📖 Consulte o [**Guia de Introdução do Plugin e Catálogo de Skills**](docs/get-started-plugin.md) para o passo a passo completo de instalação nos assistentes e exemplos práticos para cada uma das 8 skills disponíveis.

## 🚀 Guia Rápido (3 passos)

### 1. Configuração mínima

Mantenha a sessão do servidor MCP oficial da Microsoft autenticada para a sua organização. Em seguida, descubra projetos e equipes e grave a configuração local:

```bash
ado-team-compass setup --organization sua-organizacao
```

Revise o perfil de cada equipe (sprint com horas, sprint sem horas ou fluxo contínuo) e confirme o acesso:

```bash
ado-team-compass doctor
```

Se o assistente já tiver o servidor MCP configurado, você pode reaproveitar essa conexão com `--from-mcp-config` em vez de informar a organização de novo.

### 2. Comando principal

```bash
ado-team-compass status --team sua-equipe --format html --output relatorio.html
```

Com mais de uma equipe configurada, `--team` é obrigatório. Para a leitura no terminal, troque `--format html` por `--format markdown`.

### 3. Resultado esperado

O arquivo `relatorio.html` abre offline no navegador e mostra, no recorte da equipe:

- o veredito da janela (cabe / não cabe / dados insuficientes);
- carga conhecida versus capacidade restante;
- impedimentos e estados que ainda não estão mapeados;
- o que precisa de confirmação antes de decidir.

Nenhum número do relatório é inventado: quando um dado falta no board, a métrica aparece como parcial ou indisponível, com o motivo.

## 💡 Casos de Uso Comuns

### Daily em cinco minutos

**Problema:** a daily começa e ninguém tem um recorte único do que está aberto, bloqueado ou sem estimativa.

**Entrada:**

```bash
ado-team-compass status --team plataforma --format markdown
```

**Saída:** tabela da sprint com itens abertos, impedimentos ativos e até três pontos de atenção — por exemplo, “1 item bloqueado” e “2 itens sem trabalho restante”. Dá para colar no chat da daily ou ler em voz alta.

### A sprint cabe na capacidade restante?

**Problema:** o board está cheio, mas não está claro se as horas conhecidas cabem na reserva da equipe até o fim da janela.

**Entrada:**

```bash
ado-team-compass allocation --team plataforma --format markdown
```

**Saída:** carga conhecida por pessoa e pela equipe, capacidade restante e a classe (dentro da faixa, acima da faixa ou dados insuficientes). Exemplo típico: 28 h conhecidas contra 30 h reservadas, com um responsável acima da faixa e outro sem estimativa completa — sem transformar isso em ranking de produtividade.

### Conferir um número que gerou dúvida

**Problema:** alguém questiona um total do relatório (“de onde saíram essas 18 horas?”).

**Entrada:**

```bash
ado-team-compass evidence --run 20260915T120000-demo --reference 108
```

**Saída:** a evidência local daquele item (estado, responsável, trabalho restante), para reconciliar o total sem voltar a vasculhar o board à mão.

## ❓ Dúvidas Frequentes (FAQ)

**Preciso colar um PAT ou token do Azure DevOps no Compass?**
Não. A ferramenta não aceita e não armazena credencial do Azure DevOps. A sessão fica no servidor MCP oficial da Microsoft. Se o acesso expirar, renove essa sessão e rode `ado-team-compass doctor` de novo.

**O que preciso ter instalado?**
Python 3.11 ou superior. Para dados reais, a sessão autenticada do MCP oficial da sua organização. Sem essa sessão, funcionam apenas `demo` e a leitura de relatórios já gerados (`report`, `render`, `evidence`, `replay`).

**O relatório veio “parcial”. É um erro?**
Em geral, não. Significa que faltou algum dado no board — item sem horas, estado não mapeado, folga da equipe ausente. O Compass prefere marcar a lacuna a preencher com zero. Corrija o dado na origem ou o mapeamento de estados e rode `status` de novo.

## 💬 Suporte e Feedback

Encontrou um número inconsistente, um perfil que não representa o seu time ou uma tela que poderia ser mais clara? Abra uma [Issue](https://github.com/LuisCarlosLopes/ado-team-compass/issues) descrevendo a equipe (sem dados sensíveis), o comando usado e o resultado esperado.

Sugestões de funcionalidade também são bem-vindas pela mesma página: use o modelo de issue mais próximo do seu caso para acelerar a triagem.

Para detalhes sobre a política atual de submissão de código e Pull Requests, consulte as [Diretrizes de Contribuição](CONTRIBUTING.md).

