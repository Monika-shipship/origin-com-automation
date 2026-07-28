from pathlib import Path

import pytest
from pydantic import ValidationError

from origin_com_automation.workflows.spec import WorkflowSpec, workflow_spec_digest


def _spec(tmp_path: Path, **changes) -> WorkflowSpec:
    source = tmp_path / "input.csv"
    source.write_text("x,y\n1,2\n", encoding="utf-8")
    data = {
        "intent": "fit_and_plot",
        "sources": [
            {
                "id": "source",
                "path": str(source),
                "worksheet_ref": "[Book1]Data",
            }
        ],
        "data_contract": {"roles": {"x": "A", "y": ["B"]}},
        "scientific_contract": {
            "branch": "forward",
            "fit_method": "ordinary_least_squares",
            "input_units": {"x": "V", "y": "A"},
            "output_units": {"slope": "A/V"},
        },
        "analyses": [
            {
                "id": "fit",
                "method": "linear_fit",
                "worksheet_ref": "[Book1]Data",
                "x_column": "A",
                "y_columns": ["B"],
            }
        ],
        "plots": [
            {
                "id": "plot",
                "graph_type": "line",
                "roles": {"x": "A", "y": ["B"]},
            }
        ],
        "outputs": {"project_path": str(tmp_path / "result.opju")},
    }
    data.update(changes)
    return WorkflowSpec.model_validate(data)


def test_workflow_spec_has_native_fail_fast_non_overwrite_defaults(tmp_path: Path):
    spec = _spec(tmp_path)

    assert spec.sources[0].import_mode == "linked"
    assert spec.execution.backend_policy == "origin_native_preferred"
    assert spec.execution.fail_fast is True
    assert spec.outputs.overwrite == "error"
    assert spec.analyses[0].create_operation is True
    assert spec.analyses[0].recalculate_mode == "auto"
    assert spec.execution.checkpoint_policy == "auto"
    assert spec.outputs.manifest_formats == []
    assert spec.qa.reopen_project is False


@pytest.mark.parametrize("policy", ["auto", "none", "milestone", "phase", "mutation"])
def test_workflow_spec_accepts_balanced_and_legacy_recovery_policies(
    tmp_path: Path,
    policy: str,
):
    spec = _spec(tmp_path, execution={"checkpoint_policy": policy})

    assert spec.execution.checkpoint_policy == policy


def test_workflow_spec_forbids_unknown_fields(tmp_path: Path):
    with pytest.raises(ValidationError, match="extra_forbidden"):
        _spec(tmp_path, mystery=True)


@pytest.mark.parametrize(
    "replacement",
    [
        {"branch": "reverse", "fit_method": "ordinary_least_squares"},
        {"branch": "forward", "fit_method": "weighted_least_squares"},
        {"branch": "forward", "derivative_method": "central"},
        {"branch": "forward", "physical_definition": "normalized current"},
    ],
)
def test_digest_changes_with_scientific_choice(tmp_path: Path, replacement):
    baseline = _spec(tmp_path)
    changed = _spec(tmp_path, scientific_contract=replacement)

    assert workflow_spec_digest(baseline) != workflow_spec_digest(changed)


def test_digest_is_stable_for_equivalent_specs(tmp_path: Path):
    first = _spec(tmp_path)
    second = WorkflowSpec.model_validate(first.model_dump(mode="json"))

    assert workflow_spec_digest(first) == workflow_spec_digest(second)


def test_analysis_requires_unique_ids_and_columns(tmp_path: Path):
    analysis = {
        "id": "fit",
        "method": "linear_fit",
        "worksheet_ref": "[Book1]Data",
        "x_column": "A",
        "y_columns": ["B"],
    }
    with pytest.raises(ValidationError, match="analysis ids must be unique"):
        _spec(tmp_path, analyses=[analysis, analysis])

    with pytest.raises(ValidationError, match="y_columns"):
        _spec(tmp_path, analyses=[{**analysis, "y_columns": []}])


def test_fit_intent_requires_an_explicit_analysis_step(tmp_path: Path):
    with pytest.raises(ValidationError, match="fit_and_plot requires at least one analysis step"):
        _spec(tmp_path, analyses=[])


def test_native_operation_qa_rejects_non_operation_analysis_modes(tmp_path: Path):
    analysis = {
        "id": "fit",
        "method": "linear_fit",
        "worksheet_ref": "[Book1]Data",
        "x_column": "A",
        "y_columns": ["B"],
        "create_operation": False,
        "recalculate_mode": "none",
    }
    with pytest.raises(ValidationError, match="require_native_operations"):
        _spec(tmp_path, analyses=[analysis])

    with pytest.raises(ValidationError, match="require_native_operations"):
        _spec(tmp_path, execution={"backend_policy": "external_explicit"})
