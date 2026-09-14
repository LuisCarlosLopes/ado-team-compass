"""Catálogo de ferramentas MCP expostas pelo motor.

Cada ferramenta é um envelope fino sobre uma entrada da CLI: mesmo handler, mesmas fórmulas,
mesmos códigos de saída. O catálogo define apenas o nome, o schema de entrada e como os
argumentos viram argv — nenhuma regra de métrica aparece aqui.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

__all__ = ["PARAMETERS", "TOOLS", "Parameter", "ToolSpec", "tool_by_name"]


@dataclass(frozen=True)
class Parameter:
    """Opção da CLI exposta como propriedade do schema de entrada da ferramenta."""

    name: str
    flag: str
    description: str
    json_type: str = "string"
    enum: tuple[str, ...] = ()
    repeatable: bool = False

    def schema(self) -> dict[str, Any]:
        entry: dict[str, Any] = {"description": self.description}
        if self.repeatable:
            entry["type"] = "array"
            entry["items"] = {"type": self.json_type}
        else:
            entry["type"] = self.json_type
        if self.enum:
            entry["enum"] = list(self.enum)
        return entry

    def argv(self, value: Any) -> list[str]:
        """Converte o valor recebido em argumentos.

        Opções com valor usam a forma `--opcao=valor` em um único elemento: assim um valor que
        comece com hífen nunca é reinterpretado como outra opção pelo parser.
        """
        if self.json_type == "boolean":
            return [self.flag] if bool(value) else []
        if self.repeatable:
            if not isinstance(value, list):
                msg = f"o parâmetro {self.name!r} espera uma lista"
                raise ValueError(msg)
            return [f"{self.flag}={item}" for item in value]
        return [f"{self.flag}={value}"]


def _parameters() -> dict[str, Parameter]:
    declared = (
        Parameter("team", "--team", "Equipe por ID ou alias inequívoco."),
        Parameter(
            "format",
            "--format",
            "Formato da saída do motor.",
            enum=("json", "markdown", "html"),
        ),
        Parameter("as_of", "--as-of", "Instante de referência ISO-8601 do cálculo."),
        Parameter("period", "--period", "Período da análise (iteração atual ou intervalo ISO)."),
        Parameter("run", "--run", "ID de uma execução já persistida localmente."),
        Parameter("reference", "--reference", "Referência de evidência dentro da execução."),
        Parameter("organization", "--organization", "Organização do Azure DevOps."),
        Parameter(
            "with_history",
            "--with-history",
            "Inclui coleta histórica quando o catálogo conectado suportar.",
            json_type="boolean",
        ),
        Parameter(
            "offline",
            "--offline",
            "Proíbe qualquer chamada ao MCP e usa apenas dados locais.",
            json_type="boolean",
        ),
        Parameter("config", "--config", "Caminho explícito do arquivo de configuração."),
        Parameter(
            "from_mcp_config",
            "--from-mcp-config",
            "Reaproveita um servidor MCP oficial já configurado no host.",
        ),
        Parameter(
            "mcp_server",
            "--mcp-server",
            "Nome do servidor dentro da configuração de MCP do host (padrão: ado).",
        ),
        Parameter(
            "profile",
            "--profile",
            "Perfil de gestão de uma equipe, no formato ALIAS=PERFIL.",
            repeatable=True,
        ),
        Parameter(
            "force",
            "--force",
            "Autoriza sobrescrever a configuração local existente.",
            json_type="boolean",
        ),
        Parameter(
            "output",
            "--output",
            "Arquivo local de saída; padrão é a resposta da ferramenta.",
        ),
    )
    return {parameter.name: parameter for parameter in declared}


#: Opções da CLI que podem ser expostas às ferramentas, por nome.
PARAMETERS: Mapping[str, Parameter] = _parameters()


@dataclass(frozen=True)
class ToolSpec:
    """Uma ferramenta MCP e a entrada da CLI que ela executa."""

    name: str
    command: str
    title: str
    description: str
    parameters: tuple[str, ...] = ()
    required: tuple[str, ...] = ()
    fixed: tuple[str, ...] = ()
    read_only: bool = True
    reaches_ado: bool = False

    def input_schema(self) -> dict[str, Any]:
        properties = {name: PARAMETERS[name].schema() for name in self.parameters}
        schema: dict[str, Any] = {
            "type": "object",
            "properties": properties,
            "additionalProperties": False,
        }
        if self.required:
            schema["required"] = list(self.required)
        return schema

    def argv(self, arguments: Mapping[str, Any]) -> list[str]:
        """Monta o argv da CLI a partir dos argumentos recebidos pela ferramenta."""
        unknown = sorted(set(arguments) - set(self.parameters))
        if unknown:
            msg = f"parâmetros não aceitos por {self.name!r}: {', '.join(unknown)}"
            raise ValueError(msg)
        missing = sorted(name for name in self.required if arguments.get(name) in (None, ""))
        if missing:
            msg = f"parâmetros obrigatórios ausentes em {self.name!r}: {', '.join(missing)}"
            raise ValueError(msg)
        argv = [self.command, *self.fixed]
        for name in self.parameters:
            value = arguments.get(name)
            if value is None:
                continue
            argv.extend(PARAMETERS[name].argv(value))
        return argv


_COLLECTION = ("team", "format", "as_of", "period", "config", "offline")
_PERSISTED = ("team", "run", "format", "config")

#: Ferramentas anunciadas ao host. Uma por entrada da CLI que faz sentido pelo assistente:
#: `decisions` e `forecast` continuam fora, porque exigem arquivo humano ou premissa explícita.
TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="atc_version",
        command="version",
        title="Versão do motor",
        description=(
            "Informa a versão do motor e do schema de artefatos. Use para confirmar que o "
            "servidor respondeu antes de investigar qualquer outra falha."
        ),
    ),
    ToolSpec(
        name="atc_doctor",
        command="doctor",
        title="Diagnóstico do ambiente",
        description=(
            "Verifica configuração local, sessão do MCP oficial da Microsoft e as operações "
            "disponíveis no catálogo conectado. Saída 3 significa autenticação a renovar no "
            "servidor oficial, nunca credencial a informar aqui."
        ),
        parameters=("config", "format", "offline"),
        reaches_ado=True,
    ),
    ToolSpec(
        name="atc_login",
        command="login",
        title="Autorizar leitura no servidor remoto oficial",
        description=(
            "Conduz a autorização de leitura do servidor MCP remoto oficial no navegador do "
            "usuário e confirma o acesso com um handshake. Use quando outra ferramenta "
            "responder saída 3 com autorização ausente. Nenhuma senha, PAT ou token é pedido "
            "ou visto pelo Compass: quem autentica é o provedor de identidade da organização. "
            "Não se aplica a conexões stdio, onde a credencial pertence ao ambiente do host."
        ),
        parameters=("organization", "team", "config", "format"),
        read_only=False,
        reaches_ado=True,
    ),
    ToolSpec(
        name="atc_logout",
        command="logout",
        title="Apagar a autorização local",
        description=(
            "Apaga o material de autorização guardado nesta máquina. Não revoga a concessão no "
            "provedor de identidade da organização — isso é feito lá, não aqui."
        ),
        parameters=("organization", "team", "config", "format"),
        read_only=False,
    ),
    ToolSpec(
        name="atc_setup",
        command="setup",
        title="Descoberta e configuração",
        description=(
            "Descobre projetos e equipes pelo MCP oficial e grava a configuração local em "
            ".ado-team-compass/config.yaml. Nunca escreve no Azure DevOps. O perfil de gestão "
            "de cada equipe é decisão humana: confirme antes de gravar."
        ),
        parameters=("organization", "from_mcp_config", "mcp_server", "profile", "force", "config"),
        fixed=("--non-interactive",),
        read_only=False,
        reaches_ado=True,
    ),
    ToolSpec(
        name="atc_status",
        command="status",
        title="Situação atual da equipe",
        description=(
            "Coleta a situação atual e devolve o relatório da equipe: itens abertos, carga "
            "conhecida, capacidade restante, gap e impedimentos. Persiste a execução local "
            "para auditoria."
        ),
        parameters=(*_COLLECTION, "with_history", "output"),
        read_only=False,
        reaches_ado=True,
    ),
    ToolSpec(
        name="atc_history",
        command="history",
        title="Histórico de compromisso e fluxo",
        description=(
            "Coleta com histórico e devolve compromisso atendido, vazamento de escopo e fluxo "
            "quando o catálogo conectado oferecer cobertura. Sem cobertura, a saída é 5 e a "
            "métrica permanece marcada como indisponível."
        ),
        parameters=_COLLECTION,
        read_only=False,
        reaches_ado=True,
    ),
    ToolSpec(
        name="atc_planning",
        command="planning",
        title="Achados de planejamento",
        description=(
            "Aplica as regras de planejamento habilitadas para a equipe e devolve os achados: "
            "itens sem estimativa, sobrealocação e datas incoerentes. Achado é sinal para "
            "conversa, não veredito sobre pessoas."
        ),
        parameters=_COLLECTION,
        read_only=False,
        reaches_ado=True,
    ),
    ToolSpec(
        name="atc_allocation",
        command="allocation",
        title="Carga conhecida por pessoa",
        description=(
            "Distribuição da carga conhecida versus capacidade por pessoa, a partir de uma "
            "execução já persistida. Não produz ranking e não deduz ociosidade: ausência de "
            "registro é ausência de registro."
        ),
        parameters=_PERSISTED,
    ),
    ToolSpec(
        name="atc_evidence",
        command="evidence",
        title="Evidência de um valor",
        description=(
            "Recupera a evidência local que sustenta um valor do relatório, por execução e "
            "referência. Não faz nova leitura do Azure DevOps."
        ),
        parameters=(*_PERSISTED, "reference"),
    ),
    ToolSpec(
        name="atc_report",
        command="report",
        title="Relatório de uma execução persistida",
        description=(
            "Renderiza um relatório já calculado, sem nova leitura do MCP. Use para reabrir o "
            "mesmo recorte e conferir de onde veio cada valor."
        ),
        parameters=(*_PERSISTED, "output"),
    ),
    ToolSpec(
        name="atc_render",
        command="render",
        title="Relatório HTML offline",
        description=(
            "Gera o HTML autocontido de uma execução persistida e devolve o caminho do arquivo "
            "local gravado. Abre no navegador sem rede."
        ),
        parameters=(*_PERSISTED, "output"),
        read_only=False,
    ),
    ToolSpec(
        name="atc_replay",
        command="replay",
        title="Recálculo com entradas congeladas",
        description=(
            "Recalcula as métricas de uma execução a partir das entradas congeladas e informa "
            "se o resultado é idêntico. Saída 6 indica schema incompatível entre versões."
        ),
        parameters=_PERSISTED,
    ),
    ToolSpec(
        name="atc_demo",
        command="demo",
        title="Demonstração sem credencial",
        description=(
            "Gera um relatório completo com dados sintéticos, sem credencial e sem rede. Os "
            "números são fictícios: servem para explicar formato e limites, nunca para "
            "descrever uma equipe real."
        ),
        parameters=("format", "as_of", "output"),
        read_only=False,
    ),
)


def tool_by_name(name: str) -> ToolSpec:
    """Ferramenta anunciada com esse nome; erro de entrada quando não existir."""
    for tool in TOOLS:
        if tool.name == name:
            return tool
    msg = f"ferramenta desconhecida: {name!r}"
    raise ValueError(msg)
