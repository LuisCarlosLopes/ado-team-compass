# ADO Team Compass — Google Antigravity

Bundle gerado a partir de `integrations/shared/`. Não edite os arquivos deste diretório: as
instruções compartilhadas vivem na fonte comum e os bundles são regenerados por
`python packaging/build_bundles.py`.

## Instalação

1. Instale o motor no ambiente do usuário:

   ```
   pip install ado-team-compass==0.1.0
   ```

2. Configure o servidor MCP oficial do Azure DevOps na configuração de MCP do Antigravity, apontando para o servidor remoto oficial da organização.
3. Instale este bundle conforme o procedimento do Google Antigravity.
4. Valide com `ado-team-compass doctor` e, sem credencial, com `ado-team-compass demo`.

## Limites

Somente leitura: nenhuma alteração é feita no Azure DevOps. Sem servidor MCP oficial
conectado, apenas `demo`, `replay`, `report`, `render` e `evidence` funcionam. Compatibilidade
com esta versão do host precisa ser verificada em instalação real antes de ser declarada.
