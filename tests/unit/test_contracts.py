"""T02 — contratos tipados: fixtures válidas, estados distintos e unidades preservadas."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from ado_team_compass.contracts.common import (
    Coverage,
    MetricStatus,
    Quantity,
    SchemaVersion,
    Window,
)
from ado_team_compass.contracts.decisions import DecisionLog
from ado_team_compass.contracts.facts import FactSet
from ado_team_compass.contracts.metrics import Metric, MetricSet, Summary
from ado_team_compass.contracts.narrative import Narrative
from ado_team_compass.contracts.run import RunManifest
from ado_team_compass.schemas import CONTRACTS, export_schemas, schema_of

FIXTURES = Path("tests/fixtures/contracts")

MODELS: dict[str, type[BaseModel]] = {
    "run": RunManifest,
    "facts": FactSet,
    "metrics": MetricSet,
    "summary": Summary,
    "narrative": Narrative,
    "decisions": DecisionLog,
}


@pytest.mark.parametrize("name", sorted(MODELS))
def test_fixture_of_every_contract_validates(name):
    payload = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    model = MODELS[name].model_validate(payload)
    # Ida e volta preserva o contrato.
    assert MODELS[name].model_validate(model.model_dump(mode="json")) == model


def test_every_exported_contract_has_a_fixture_or_is_configuration():
    assert set(CONTRACTS) == set(MODELS) | {"config"}


def test_missing_zero_and_not_applicable_are_distinct():
    missing = Quantity(unit="hours")
    zero = Quantity(value=Decimal(0), unit="hours")
    assert missing.is_missing and not zero.is_missing
    assert missing != zero

    not_applicable = Metric(
        id="observed_utilization",
        definition_version="1.0",
        status=MetricStatus.NOT_APPLICABLE,
        unavailable_reason="equipe sem capacidade em horas",
    )
    empty_sample = Metric(
        id="throughput",
        definition_version="1.0",
        status=MetricStatus.AVAILABLE,
        quantity=Quantity(value=Decimal(0), unit="items"),
    )
    assert not_applicable.quantity is None
    assert empty_sample.quantity is not None and empty_sample.quantity.value == 0


def test_unavailable_metric_requires_reason():
    with pytest.raises(ValidationError):
        Metric(id="x", definition_version="1.0", status=MetricStatus.UNAVAILABLE)


def test_incompatible_units_are_not_aggregated():
    with pytest.raises(ValueError, match="unidades incompatíveis"):
        Quantity(value=Decimal(8), unit="hours").add(Quantity(value=Decimal(1), unit="days"))


def test_sum_of_missing_values_stays_missing():
    total = Quantity(unit="hours").add(Quantity(unit="hours"))
    assert total.is_missing


def test_missing_plus_value_is_a_lower_bound_not_zero_substitution():
    total = Quantity(unit="hours").add(Quantity(value=Decimal(16), unit="hours"))
    assert total.value == Decimal(16)


def test_unknown_denominator_yields_unknown_coverage_not_full():
    unknown = Coverage(valid=5)
    assert unknown.ratio is None and not unknown.is_known
    assert Coverage(eligible=4, valid=3).ratio == Decimal(3) / Decimal(4)


def test_coverage_rejects_valid_above_eligible():
    with pytest.raises(ValidationError):
        Coverage(eligible=2, valid=3)


def test_window_requires_exclusive_end():
    with pytest.raises(ValidationError):
        Window(
            start="2026-09-12T00:00:00Z", end="2026-09-12T00:00:00Z", timezone="America/Sao_Paulo"
        )


def test_schema_version_parsing_is_strict():
    assert str(SchemaVersion.parse("1.2")) == "1.2"
    with pytest.raises(ValueError, match="Versão de schema inválida"):
        SchemaVersion.parse("1")


def test_contracts_reject_unknown_fields():
    with pytest.raises(ValidationError):
        MetricSet.model_validate({"run_id": "r", "team_id": "t", "extra": 1})


def test_decisions_are_deduplicated_by_stable_id():
    payload = json.loads((FIXTURES / "decisions.json").read_text(encoding="utf-8"))
    duplicated = DecisionLog.model_validate(
        {"decisions": [*payload["decisions"], *payload["decisions"]]}
    )
    assert len(duplicated.decisions) == 2
    assert len(duplicated.deduplicated()) == 1


def test_schemas_export_one_file_per_contract(tmp_path):
    written = export_schemas(tmp_path)
    assert [path.name for path in written] == [f"{name}.schema.json" for name in sorted(CONTRACTS)]
    schema = schema_of("config")
    assert schema["x-schema-major"] == 1
    assert "teams" in schema["properties"]
