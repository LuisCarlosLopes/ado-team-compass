# Implantação do gateway de leitura

Estado: topologia recomendada; nada foi implantado por este repositório.

## Topologia inicial

Um serviço dedicado por organização, com:

- uma instância de leitura da API (`ado-team-compass[api]`), sem acesso ao Azure DevOps;
- um coletor agendado separado, que usa exclusivamente o MCP oficial da Microsoft;
- um volume de relatórios escrito atomicamente pelo coletor e montado como somente leitura
  pela API.

SaaS multi-tenant continua fora de escopo.

## Serviço

```bash
pip install "ado-team-compass[api]==<versão>"
uvicorn "ado_team_compass.gateway.factory:application" --host 0.0.0.0 --port 8080
```

O processo precisa das variáveis de ambiente:

| Variável | Conteúdo |
|---|---|
| `COMPASS_RUNS_DIR` | Volume de execuções, montado somente leitura |
| `COMPASS_ACL_FILE` | ACL de equipes por usuário, relida a cada requisição |
| `COMPASS_OIDC_ISSUER` | Emissor esperado do token |
| `COMPASS_OIDC_AUDIENCE` | Audiência esperada do token |
| `COMPASS_OIDC_JWKS_URL` | JWKS do provedor corporativo |

## ACL

```json
{
  "organization": "contoso",
  "users": {
    "pessoa@empresa.com": ["plataforma"],
    "gestora@empresa.com": ["plataforma", "suporte"]
  }
}
```

Negativa por padrão: usuário ausente do arquivo não tem acesso a nada. A ACL é lida a cada
requisição, então revogar acesso vale já na requisição seguinte.

## Limites operacionais

- Somente GET; nenhuma rota dispara coleta.
- Um `run_id` não é autorização: a equipe dona da execução é revalidada em toda consulta.
- Os relatórios podem conter nomes e dados internos. Trate o volume e os backups como
  material restrito e prefira retenção curta.
