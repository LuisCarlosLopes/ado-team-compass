# ADO Team Compass — Claude Code

Bundle gerado a partir de `integrations/shared/`. Não edite os arquivos deste diretório: as
instruções compartilhadas vivem na fonte comum e os bundles são regenerados por
`python packaging/build_bundles.py`.

Versão do motor: 0.2.0

## Instalação

1. Instale este bundle conforme o procedimento do Claude Code.
2. O manifesto deste bundle já declara o servidor `ado-team-compass`; o Claude Code o sobe junto com o plugin.
3. Configure o servidor MCP oficial do Azure DevOps no próprio Claude Code (`claude mcp add`), apontando para o servidor remoto oficial da organização.
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
