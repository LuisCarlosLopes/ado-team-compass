"""T11 — execução persistida, relatório determinístico, resumo limitado e replay (V14).

Expectativas calculadas da fixture sintética: 8 itens contabilizáveis no nível task folha,
6 abertos, carga conhecida 28 h (dois itens abertos sem restante), capacidade restante
30 h em 15/09 (dia corrente excluído: 16, 17 e 18; Ana de folga em 16) e utilização 93,3%.
"""

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ado_team_compass.adapters.ado_mcp import AdoMcpClient
from ado_team_compass.cli import main
from ado_team_compass.config import resolve_config
from ado_team_compass.contracts.common import MetricStatus
from ado_team_compass.contracts.metrics import Summary
from ado_team_compass.contracts.report import TeamReport
from ado_team_compass.contracts.run import RunState
from ado_team_compass.demo import ORGANIZATION, demo_config_document, transport
from ado_team_compass.errors import CollectError, ConfigError, ExitCode
from ado_team_compass.pipeline import execute_status, replay_run
from ado_team_compass.reporting import build_summary, render_markdown
from ado_team_compass.runs import RunStore

AS_OF = datetime.fromisoformat("2026-09-15T12:00:00-03:00")


def _execute(tmp_path: Path, responses=None, tools=None):
    resolved = resolve_config(demo_config_document())
    team = resolved.config.teams[0]
    kwargs = {}
    if tools is not None:
        kwargs["tools"] = tools
    client = AdoMcpClient(transport=transport(responses, **kwargs))
    client.handshake()
    store = RunStore(tmp_path / "runs")
    outcome = execute_status(
        client,
        team,
        organization=ORGANIZATION,
        as_of=AS_OF,
        store=store,
        resolved=resolved,
    )
    return outcome, store, resolved


def test_execution_persists_every_artifact_with_hashes(tmp_path):
    outcome, store, _ = _execute(tmp_path)
    run = store.load(outcome.run.manifest.run_id)
    assert sorted(run.manifest.artifact_hashes) == [
        "facts.json",
        "metrics.json",
        "report.json",
        "summary.json",
    ]
    assert run.verify() == ()
    assert (run.directory / "report.md").is_file()
    assert (run.directory / "evidence" / "items" / "101.json").is_file()


def test_numbers_match_the_hand_calculated_expectations(tmp_path):
    outcome, _, _ = _execute(tmp_path)
    report = outcome.report
    load = report.metric("known_remaining_work")
    capacity = report.metric("reserved_remaining_capacity")
    utilization = report.metric("observed_utilization")
    assert load is not None and load.quantity is not None
    assert load.quantity.value == Decimal(28)
    assert load.status is MetricStatus.PARTIAL
    assert load.coverage.valid == 4 and load.coverage.eligible == 6
    assert capacity is not None and capacity.quantity is not None
    assert capacity.quantity.value == Decimal(30)
    assert utilization is not None and utilization.ratio is not None
    assert utilization.ratio.quantize(Decimal("0.001")) == Decimal("0.933")
    assert utilization.status is MetricStatus.PARTIAL


def test_person_rows_keep_overload_visible_and_suppress_false_low_load(tmp_path):
    outcome, _, _ = _execute(tmp_path)
    rows = {row.person_id: row for row in outcome.report.people}
    ana = rows["person-ana"]
    bruno = rows["person-bruno"]
    assert ana.known_load.value == Decimal(18)
    assert ana.reserved_capacity is not None and ana.reserved_capacity.value == Decimal(12)
    assert ana.load_class == "ACIMA_DA_FAIXA" and ana.is_lower_bound
    assert bruno.load_class == "DADOS_INSUFICIENTES"
    assert bruno.items_missing == 1


def test_every_number_traces_to_metrics_and_evidence(tmp_path):
    outcome, store, _ = _execute(tmp_path)
    run = store.load(outcome.run.manifest.run_id)
    metrics = run.artifact("metrics.json")
    report = TeamReport.model_validate(run.artifact("report.json"))
    assert [metric["id"] for metric in metrics["metrics"]] == [
        metric.id for metric in report.metrics
    ]
    for finding in report.findings:
        for reference in finding.evidence:
            assert (run.directory / reference).is_file()
    assert set(report.evidence_references.values()) <= {
        f"evidence/items/{item_id}.json" for item_id in report.evidence_references
    }


def test_partial_sources_make_the_run_partial_and_exit_five(tmp_path):
    outcome, _, _ = _execute(tmp_path)
    assert outcome.run.manifest.state is RunState.PARTIAL
    assert outcome.exit_code is ExitCode.PARTIAL_CAPABILITY
    assert any("metrica_parcial" in reason for reason in outcome.run.manifest.partial_reasons)


def test_complete_run_when_every_item_has_remaining_work(tmp_path):
    from ado_team_compass.demo.dataset import WORK_ITEMS

    complete_items = []
    for item in WORK_ITEMS:
        fields = dict(item["fields"])
        if fields["System.State"] == "Committed" and item["id"] != 100:
            fields["Microsoft.VSTS.Scheduling.RemainingWork"] = fields.get(
                "Microsoft.VSTS.Scheduling.RemainingWork", 4
            )
        if fields["System.State"] == "Em análise":
            fields["System.State"] = "Committed"
        complete_items.append({"id": item["id"], "fields": fields})
    responses = {
        **__import__(
            "ado_team_compass.demo.dataset", fromlist=["default_responses"]
        ).default_responses(),
        "wit_get_work_items_batch": {"value": complete_items},
        "work_get_team_capacity": {
            **__import__("ado_team_compass.demo.dataset", fromlist=["CAPACITY"]).CAPACITY,
            "teamDaysOff": [],
        },
    }
    outcome, _, _ = _execute(tmp_path, responses)
    load = outcome.report.metric("known_remaining_work")
    assert load is not None and load.status is MetricStatus.AVAILABLE


# V14 — replay com fatos e versões congelados.
def test_v14_replay_reproduces_identical_metrics(tmp_path):
    outcome, store, resolved = _execute(tmp_path)
    report, identical = replay_run(store, outcome.run.manifest.run_id, resolved=resolved)
    assert identical
    assert (
        report.model_dump(mode="json")["metrics"]
        == outcome.report.model_dump(mode="json")["metrics"]
    )


def test_v14_replay_does_not_depend_on_the_clock(tmp_path, monkeypatch):
    outcome, store, resolved = _execute(tmp_path)

    class FrozenElsewhere(datetime):
        @classmethod
        def now(cls, tz=None):  # pragma: no cover - só prova que não é consultado
            raise AssertionError("o replay não pode consultar o relógio do sistema")

    monkeypatch.setattr("ado_team_compass.metrics.engine.datetime", FrozenElsewhere)
    _, identical = replay_run(store, outcome.run.manifest.run_id, resolved=resolved)
    assert identical


def test_replay_of_unknown_team_is_actionable(tmp_path):
    outcome, store, resolved = _execute(tmp_path)
    with pytest.raises(ConfigError) as error:
        replay_run(store, outcome.run.manifest.run_id, resolved=resolved, team_alias="inexistente")
    assert error.value.code == "E_REPLAY_EQUIPE_AUSENTE"


# -- resumo -------------------------------------------------------------------------
def test_summary_keeps_totals_and_limitations_when_truncating(tmp_path):
    outcome, _, _ = _execute(tmp_path)
    many_findings = tuple(
        outcome.report.findings[0].model_copy(
            update={"id": f"f{index}", "message": "achado sintético " * 20}
        )
        for index in range(200)
    )
    report = outcome.report.model_copy(update={"findings": many_findings})
    summary = build_summary(report, limit_bytes=4096)
    assert summary.truncated
    assert summary.truncation_reference is not None
    assert len(summary.findings) < len(many_findings)
    assert len(summary.metrics) == len(report.metrics)
    assert summary.limitations == report.limitations
    payload = json.dumps(summary.model_dump(mode="json"), ensure_ascii=False)
    assert len(payload.encode("utf-8")) <= 4096


def test_summary_within_limit_is_not_truncated(tmp_path):
    outcome, store, _ = _execute(tmp_path)
    summary = Summary.model_validate(
        store.load(outcome.run.manifest.run_id).artifact("summary.json")
    )
    assert not summary.truncated
    assert summary.truncation_reference is None


def test_summary_findings_are_ordered_deterministically(tmp_path):
    outcome, _, _ = _execute(tmp_path)
    findings = (
        outcome.report.findings[0].model_copy(update={"id": "b", "severity": "info"}),
        outcome.report.findings[0].model_copy(update={"id": "a", "severity": "critico"}),
    )
    summary = build_summary(outcome.report.model_copy(update={"findings": findings}))
    assert [finding.id for finding in summary.findings] == ["a", "b"]


# -- renderização e falhas ----------------------------------------------------------
def test_markdown_is_deterministic_and_declares_its_origin(tmp_path):
    outcome, _, _ = _execute(tmp_path)
    first = render_markdown(outcome.report)
    assert first == render_markdown(outcome.report)
    assert "Nenhum número desta página foi produzido por modelo de linguagem." in first
    assert "28 hours" in first


def test_interrupted_write_does_not_replace_a_valid_run(tmp_path):
    outcome, store, resolved = _execute(tmp_path)
    valid_id = outcome.run.manifest.run_id

    broken = {
        **__import__(
            "ado_team_compass.demo.dataset", fromlist=["default_responses"]
        ).default_responses(),
        "wit_get_work_items_batch": [CollectError("E_MCP_TIMEOUT", "timeout")] * 3,
    }
    resolved_config = resolve_config(demo_config_document())
    client = AdoMcpClient(transport=transport(broken))
    client.handshake()
    later = AS_OF.replace(hour=13)
    from ado_team_compass.pipeline import execute_status as execute

    outcome_two = execute(
        client,
        resolved_config.config.teams[0],
        organization=ORGANIZATION,
        as_of=later,
        store=store,
        resolved=resolved_config,
    )
    # A coleta trata o lote perdido como cobertura parcial, não como execução inválida.
    assert outcome_two.run.manifest.state is RunState.PARTIAL
    assert store.load(valid_id).manifest.run_id == valid_id
    assert resolved.config.teams[0].alias == "demo"


def test_access_failure_abandons_the_run_without_a_manifest(tmp_path):
    from ado_team_compass.errors import AccessError
    from ado_team_compass.mcp.session.transport import ToolCallResult

    responses = {
        **__import__(
            "ado_team_compass.demo.dataset", fromlist=["default_responses"]
        ).default_responses(),
        "work_list_team_iterations": ToolCallResult(
            tool="work_list_team_iterations", is_error=True, error_text="403 forbidden"
        ),
    }
    resolved = resolve_config(demo_config_document())
    client = AdoMcpClient(transport=transport(responses))
    client.handshake()
    store = RunStore(tmp_path / "runs")
    with pytest.raises(AccessError):
        execute_status(
            client,
            resolved.config.teams[0],
            organization=ORGANIZATION,
            as_of=AS_OF,
            store=store,
            resolved=resolved,
        )
    assert store.list_runs() == ()
    run_id = "20260915T120000-demo"
    assert (tmp_path / "runs" / run_id / "INCOMPLETA.txt").is_file()


def test_cli_demo_runs_without_network_and_emits_markdown(tmp_path, capsys):
    assert main(["demo", "--format", "markdown", "--output", str(tmp_path / "demo")]) == int(
        ExitCode.PARTIAL_CAPABILITY
    )
    output = capsys.readouterr().out
    assert "Situação atual — demo" in output
    assert "28 hours" in output


def test_cli_report_and_allocation_read_the_persisted_run(tmp_path, capsys, monkeypatch):
    config_path = tmp_path / "config.yaml"
    document = demo_config_document()
    document["output"] = {"directory": str(tmp_path / "runs")}
    config_path.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setenv("ADO_TEAM_COMPASS_CONFIG", str(config_path))

    resolved = resolve_config(document)
    client = AdoMcpClient(transport=transport())
    client.handshake()
    execute_status(
        client,
        resolved.config.teams[0],
        organization=ORGANIZATION,
        as_of=AS_OF,
        store=RunStore(tmp_path / "runs"),
        resolved=resolved,
    )
    capsys.readouterr()

    assert main(["report", "--format", "markdown"]) == int(ExitCode.OK)
    assert "Situação atual — demo" in capsys.readouterr().out

    assert main(["allocation"]) == int(ExitCode.OK)
    payload = json.loads(capsys.readouterr().out)
    assert {row["person_id"] for row in payload["people"]} == {"person-ana", "person-bruno"}

    assert main(["evidence", "--reference", "101"]) == int(ExitCode.OK)
    evidence = json.loads(capsys.readouterr().out)
    assert evidence["remaining_work"] == {"value": "10", "unit": "hours"}

    assert main(["replay"]) == int(ExitCode.OK)
    replay = json.loads(capsys.readouterr().out)
    assert replay["identical"] is True


def test_cli_collect_refuses_offline(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(json.dumps(demo_config_document()), encoding="utf-8")
    monkeypatch.setenv("ADO_TEAM_COMPASS_CONFIG", str(config_path))
    assert main(["collect", "--offline"]) == int(ExitCode.INVALID_INPUT)


def test_cli_requires_unambiguous_team(tmp_path, monkeypatch, capsys):
    document = demo_config_document()
    second = dict(document["teams"][0])
    second["alias"] = "outra"
    second["team_id"] = "team-outra"
    document["teams"].append(second)
    document["output"] = {"directory": str(tmp_path / "runs")}
    config_path = tmp_path / "config.yaml"
    config_path.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setenv("ADO_TEAM_COMPASS_CONFIG", str(config_path))
    assert main(["report"]) == int(ExitCode.INVALID_INPUT)
    assert "E_EQUIPE_AMBIGUA" in capsys.readouterr().err
