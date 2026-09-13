"""T21 — release histórica integrada: relatório, HTML e regressão da v0.1.

A fixture sintética ganha revisões para exercitar baseline, escopo e fluxo; sem a ferramenta
de revisões no catálogo, a v0.1 continua funcionando sem histórico.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

import pytest

from ado_team_compass.adapters.ado_mcp import AdoMcpClient
from ado_team_compass.config import resolve_config
from ado_team_compass.demo import ORGANIZATION, demo_config_document
from ado_team_compass.demo.dataset import (
    ITERATION_PATH,
    READ_TOOLS,
    WORK_ITEMS,
    default_responses,
    transport,
)
from ado_team_compass.pipeline import execute_status
from ado_team_compass.runs import RunStore

AS_OF = datetime.fromisoformat("2026-09-18T12:00:00-03:00")
TOOLS_WITH_HISTORY = READ_TOOLS


def _revisions_for(item_id: int) -> dict[str, object]:
    """Duas revisões por item: entrada na sprint e conclusão para alguns."""
    completed = item_id in (101, 102)
    revisions = [
        {
            "rev": 1,
            "fields": {
                "System.ChangedDate": "2026-09-13T10:00:00Z",
                "System.State": "Committed",
                "System.IterationPath": ITERATION_PATH,
                "Microsoft.VSTS.Scheduling.StoryPoints": 5,
            },
        }
    ]
    if completed:
        revisions.append(
            {
                "rev": 2,
                "fields": {
                    "System.ChangedDate": "2026-09-16T10:00:00Z",
                    "System.State": "Done",
                    "System.IterationPath": ITERATION_PATH,
                    "Microsoft.VSTS.Scheduling.StoryPoints": 5,
                },
            }
        )
    return {"value": revisions}


def _run(tmp_path, *, tools=TOOLS_WITH_HISTORY, include_history=True, without_revisions=False):
    responses = {
        **default_responses(),
        "wit_work_item:list_revisions": [_revisions_for(item["id"]) for item in WORK_ITEMS],
    }
    resolved = resolve_config(demo_config_document())
    override = (
        {"wit_work_item": ("get", "get_batch", "list_for_iteration")} if without_revisions else None
    )
    client = AdoMcpClient(transport=transport(responses, tools=tools, actions_override=override))
    client.handshake()
    store = RunStore(tmp_path / "runs")
    outcome = execute_status(
        client,
        resolved.config.teams[0],
        organization=ORGANIZATION,
        as_of=AS_OF,
        store=store,
        resolved=resolved,
        include_history=include_history,
        include_planning=True,
    )
    return outcome, store


@pytest.fixture(scope="module")
def outcome(tmp_path_factory):
    return _run(tmp_path_factory.mktemp("hist"))[0]


def test_history_block_is_available_and_persisted(outcome, tmp_path_factory):
    block = outcome.report.history
    assert block is not None and block.available
    assert (outcome.run.directory / "history.json").is_file()
    assert "history.json" in outcome.run.manifest.artifact_hashes


def test_baseline_is_technical_and_say_do_counts_only_baseline_items(outcome):
    block = outcome.report.history
    assert block is not None
    assert block.baseline_is_technical
    assert block.baseline_size == len(WORK_ITEMS)
    assert (block.say_do_numerator, block.say_do_denominator) == (2, len(WORK_ITEMS))
    assert block.say_do == Decimal(2) / Decimal(len(WORK_ITEMS))


def test_flow_metrics_come_with_sample_size_and_small_sample_flag(outcome):
    block = outcome.report.history
    assert block is not None
    assert block.cycle_time_sample == 2
    assert block.small_sample
    assert block.throughput and sum(point.value for point in block.throughput) == 2


def test_html_shows_the_history_block_with_its_cohort(outcome):
    html = (outcome.run.directory / "report.html").read_text(encoding="utf-8")
    assert "Histórico observado" in html
    assert "Say/do" in html
    assert "baseline técnica" in html
    assert "nearest-rank" in html
    assert "não é tempo até valor em produção" in html


def test_markdown_shows_the_same_history_numbers(outcome):
    markdown = (outcome.run.directory / "report.md").read_text(encoding="utf-8")
    assert "## Histórico observado" in markdown
    assert "Say/do" in markdown


def test_planning_findings_are_included_and_come_from_enabled_rules_only(outcome):
    rules = {finding.rule_id for finding in outcome.report.planning_findings}
    assert rules <= {
        "inverted_dates",
        "overdue_open_item",
        "parent_ends_before_children",
        "open_work_in_closed_sprint",
        "missing_required_fields",
    }
    assert "story_without_task" not in rules
    assert "missing_estimate" not in rules


def test_v01_regression_still_works_without_history(tmp_path):
    """Catálogo sem a ação de revisões: a v0.1 continua igual, o histórico fica indisponível."""
    outcome, _ = _run(tmp_path, tools=READ_TOOLS, include_history=True, without_revisions=True)
    block = outcome.report.history
    assert block is not None and not block.available
    assert any("indisponível" in reason for reason in block.reasons)
    load = outcome.report.metric("known_remaining_work")
    assert load is not None and load.quantity is not None
    assert load.quantity.value == Decimal(28)
    html = (outcome.run.directory / "report.html").read_text(encoding="utf-8")
    assert "Nenhum dia passado é desenhado por interpolação" in html


def test_history_artifacts_validate_against_the_contract(outcome):
    from ado_team_compass.contracts.history import HistorySet

    payload = json.loads((outcome.run.directory / "history.json").read_text(encoding="utf-8"))
    assert HistorySet.model_validate(payload).coverage.is_usable


def test_forecast_entry_requires_history_and_declares_its_status(
    outcome, monkeypatch, capsys, tmp_path
):
    """T25 — a entrada `forecast` só projeta sobre execução com histórico disponível."""
    import json as _json

    from ado_team_compass.cli import main
    from ado_team_compass.errors import ExitCode

    document = demo_config_document()
    document["output"] = {"directory": str(outcome.run.directory.parent)}
    config_path = tmp_path / "config.yaml"
    config_path.write_text(_json.dumps(document), encoding="utf-8")
    monkeypatch.setenv("ADO_TEAM_COMPASS_CONFIG", str(config_path))

    code = main(["forecast", "--run", outcome.run.manifest.run_id])
    payload = _json.loads(capsys.readouterr().out)
    assert payload["status"] == "experimental"
    assert payload["seed"]
    assert payload["premises"]
    # A amostra sintética é curta: a projeção é negada com o requisito faltante.
    assert payload["available"] is False
    assert any("requisito faltante" in reason for reason in payload["reasons"])
    assert code == int(ExitCode.PARTIAL_CAPABILITY)
