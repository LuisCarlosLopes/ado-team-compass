# Diretrizes de Contribuição — ADO Team Compass

Obrigado pelo seu interesse no **ADO Team Compass**!

## 📢 Status Atual do Projeto: Público para Uso, Contribuições Fechadas

O código-fonte e os pacotes do ADO Team Compass estão **públicos e disponíveis para qualquer pessoa utilizar, avaliar e executar** em seus times e organizações com o servidor oficial do Azure DevOps MCP.

No entanto, **neste momento inicial, o projeto NÃO está aceitando contribuições externas de código (Pull Requests)**.

### Por que as contribuições estão restritas temporariamente?
1. **Consolidação Arquitetural:** O núcleo de contratos, motor determinístico e adaptadores MCP estão em rápida evolução e consolidação pelo mantenedor principal.
2. **Garantias Rígidas de Segurança:** O projeto possui invariantes inegociáveis (`MCP_ONLY`, `READ_ONLY`, `ZERO_SECRETS`), cujos testes e esteiras precisam atingir estabilidade total antes de integrarmos contribuições de múltiplos autores.
3. **Escopo e Foco:** Queremos garantir que os primeiros perfis e casos de uso de entrega estejam redondos e estáveis.

---

## 🛠️ Como você pode participar hoje?

Embora Pull Requests de código não estejam abertos no momento, seu feedback sobre o uso da ferramenta é extremamente valioso:

- **Relatar Problemas (Bugs):** Se você encontrar um erro na leitura do board, um cálculo parcial inesperado ou incompatibilidade de perfil, abra uma [Issue](https://github.com/LuisCarlosLopes/ado-team-compass/issues) com os detalhes (sem incluir credenciais ou dados sensíveis).
- **Sugerir Melhorias:** Dúvidas sobre perfis de equipe ou sugestões de novos formatos de relatório podem ser compartilhadas via [Issues](https://github.com/LuisCarlosLopes/ado-team-compass/issues).

---

## 🔄 Abertura Futura

Assim que a versão de lançamento e os contratos estiverem consolidados, atualizaremos este documento com o processo completo de submissão de código, fluxo de PRs e orientações de testes locais.

Agradecemos a compreensão e o apoio!
