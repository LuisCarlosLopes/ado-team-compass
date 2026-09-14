# ADO Team Compass — Codex

Bundle gerado a partir de `integrations/shared/`. Não edite os arquivos deste diretório: as
instruções compartilhadas vivem na fonte comum e os bundles são regenerados por
`python packaging/build_bundles.py`.

Versão do motor: 0.2.0

## Instalação

1. Instale este bundle conforme o procedimento do Codex.
2. Este host não expõe uma variável com a raiz do bundle, então a declaração do servidor não é gerada: registre `ado-team-compass` na configuração de MCP do host com o comando `python3` e o caminho absoluto de `bin/atc-mcp.py` dentro do bundle instalado. O arquivo `mcp-server.json` do bundle traz a entrada pronta para copiar.
3. Configure o servidor MCP oficial do Azure DevOps na configuração de MCP do Codex, apontando para o servidor remoto oficial da organização.
4. Valide chamando a ferramenta `atc_doctor` e, sem credencial, `atc_demo`.

Não é preciso instalar a CLI antes. O motor acompanha o pacote de release em `engine/` e
`bin/atc-mcp.py` o prepara sozinho na primeira execução, em um ambiente isolado sob
`~/.ado-team-compass/runtime`. Quando o pacote `ado-team-compass` já estiver instalado na
máquina, é essa instalação que o launcher usa.

Requisito: Python 3.12 ou superior acessível como `python3`. Se o interpretador tiver outro
nome ou você quiser fixar um ambiente específico, aponte `ADO_TEAM_COMPASS_ENGINE_PYTHON` para
o interpretador desejado. Para proibir a preparação automática, defina
`ADO_TEAM_COMPASS_NO_BOOTSTRAP=1`.

## Limites

Somente leitura: nenhuma alteração é feita no Azure DevOps. Sem servidor MCP oficial
conectado, apenas `atc_demo`, `atc_replay`, `atc_report`, `atc_render` e `atc_evidence`
funcionam. Compatibilidade com esta versão do host precisa ser verificada em instalação real
antes de ser declarada.
