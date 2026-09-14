# Matriz de Certificação de Hosts — ADO Team Compass

Documento canônico para registro e auditoria da certificação de execução nos hosts locais de IA.
Revisão: 2026-09-13 (v1.0) | Alinhado a `docs/platform-compatibility.md` e IPD `compatibilizar-plugins-hosts`.

---

## 1. Princípios de Certificação

1. **Evidência Obrigatória:** Nenhum host pode ser declarado "Testado" ou "Certificado" sem
   evidência registrada em instalação real.
2. **Isolamento de Credenciais:** Testes em host real utilizam a sessão MCP do próprio host
   ou variáveis locais; nenhum token, PAT ou segredo pode ser persistido nos bundles ou
   relatórios de evidência.
3. **Exclusividade MCP Oficial:** Toda a coleta de dados durante a certificação deve transitar
   exclusivamente pelo servidor oficial [microsoft/azure-devops-mcp](https://github.com/microsoft/azure-devops-mcp).
4. **Pureza e Paridade:** As métricas calculadas devem ser idênticas entre hosts diante do
   mesmo conjunto de fatos e relógio explícito.

---

## 2. Matriz de Certificação dos Hosts Locais

Status permitidos:
- `Planejado`: bundle implementado no repositório; teste em host real pendente.
- `Em validação`: procedimento de instalação e testes em andamento no ambiente de destino.
- `Testado`: checklist de certificação completo e evidência registrada.
- `Falhou`: anomalia impeditiva encontrada durante o teste manual no host.
- `Não suportado`: host ou versão explicitamente fora do escopo do produto.

| Host | OS | Versão Host | Versão Compass | Install | Skill Discovery | Status | Evidence | Update | Uninstall |
|---|---|---|---|---|---|---|---|---|---|
| **Claude Code** | macOS / Linux / Windows | A definir | `0.3.0` | Pendente | Pendente | `Planejado` | Nenhuma | Pendente | Pendente |
| **Google Antigravity** | macOS / Linux / Windows | A definir | `0.3.0` | Pendente | Pendente | `Planejado` | Nenhuma | Pendente | Pendente |
| **Codex** | macOS / Linux / Windows | A definir | `0.3.0` | Pendente | Pendente | `Planejado` | Nenhuma | Pendente | Pendente |
| **Cursor** | macOS / Linux / Windows | A definir | `0.3.0` | Pendente | Pendente | `Planejado` | Nenhuma | Pendente | Pendente |

> [!NOTE]
> **ChatGPT Actions / Custom GPT:** Permanece fora desta matriz local (adiado para v0.3.1).
> Exige infraestrutura remota de gateway FastAPI, domínio HTTPS com certificado válido,
> OAuth corporativo e agendamento de coletas.

---

## 3. Roteiro de Certificação Manual (Passo a Passo)

Para cada host a ser certificado, o operador deve seguir este fluxo e anexar os resultados:

### Passo 1 — Instalação do Motor Python
1. Confirmar Python 3.11 ou superior no sistema:
   ```bash
   python3 --version
   ```
2. Nada a instalar: o bundle traz o motor em `engine/` e o prepara na primeira chamada. Para
   certificar o caminho com instalação prévia, instale o wheel e repita a bateria:
   ```bash
   pip install engine/ado_team_compass-<versao>-py3-none-any.whl
   ```

### Passo 2 — Configuração do MCP Oficial no Host
Configurar o servidor oficial `azure-devops-mcp` diretamente no cliente do host:
- **Claude Code:** `claude mcp add azure-devops ...`
- **Cursor:** Adicionar em `.cursor/mcp.json` ou nas configurações de MCP do Cursor.
- **Google Antigravity:** Configuração de MCP na interface do Antigravity.
- **Codex:** Configuração de MCP no cliente Codex.

### Passo 3 — Instalação do Bundle de Plugin
- Copiar o diretório gerado em `plugin/<host>/` para a pasta de plugins do host, ou instalar
  o pacote release `ado-team-compass-<host>-<versao>.zip`.

### Passo 4 — Validação de Descoberta e Execução
1. Abrir o assistente no host e verificar se as 8 skills são listadas e reconhecidas:
   - `atc-setup`
   - `atc-doctor`
   - `atc-demo`
   - `atc-status`
   - `atc-allocation`
   - `atc-evidence`
   - `atc-history`
   - `atc-planning`
2. Confirmar que o host anunciou as 12 ferramentas do servidor `ado-team-compass`.
3. Chamar `atc_doctor` pelo assistente e registrar o `exit_code`.
4. Chamar `atc_demo` com `format: markdown` — deve funcionar sem credencial e sem rede.
5. Se o MCP oficial estiver autenticado no host, chamar `atc_status` com `team` e `format`.

### Passo 5 — Registro de Evidência e Atualização do Status
1. Salvar os logs e saída do assistente em `docs/evidence/<host>-<data>/`.
2. Sanitizar qualquer informação sensível (tokens, URLs privadas ou credenciais).
3. Atualizar a linha correspondente nesta matriz com a versão do host, sistema operacional,
   link para a evidência e status `Testado`.
