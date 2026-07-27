from pathlib import Path

from origin_com_automation.workflows.planner import compile_workflow
from origin_com_automation.workflows.spec import WorkflowSpec, workflow_spec_digest


def _derivative_spec(tmp_path: Path, **changes) -> WorkflowSpec:
    source = tmp_path / "curve.csv"
    source.write_text("Vg,Id\n0,1e-9\n1,1e-7\n2,1e-5\n", encoding="utf-8")
    data = {
        "intent": "curve_analysis",
        "sources": [
            {
                "id": "curve",
                "path": str(source),
                "worksheet_ref": "[Curve]Data",
            }
        ],
        "data_contract": {"roles": {"x": "A", "y": ["B"]}},
        "analyses": [
            {
                "id": "gm",
                "method": "derivative",
                "worksheet_ref": "[Curve]Data",
                "x_column": "A",
                "y_columns": ["B"],
            }
        ],
        "outputs": {"project_path": str(tmp_path / "curve-analysis.opju")},
    }
    data.update(changes)
    return WorkflowSpec.model_validate(data)


def test_planner_reports_all_missing_scientific_decisions_at_once(tmp_path: Path):
    spec = _derivative_spec(tmp_path)

    plan = compile_workflow(spec, origin_version="10.1.0.178")
    fields = {item["field"] for item in plan.required_decisions}

    assert plan.executor_executable is False
    assert {
        "scientific_contract.branch",
        "scientific_contract.derivative_method",
        "scientific_contract.derivative_order",
        "scientific_contract.input_units.x",
        "scientific_contract.input_units.y",
    } <= fields
    assert plan.digest == workflow_spec_digest(spec)
    assert plan.safe_defaults["fail_fast"] is True
    assert plan.safe_defaults["overwrite"] == "error"


def test_planner_inspects_sources_and_predicts_mutations_without_controller(tmp_path: Path):
    spec = _derivative_spec(
        tmp_path,
        scientific_contract={
            "branch": "forward",
            "derivative_method": "central",
            "derivative_order": 1,
            "input_units": {"x": "V", "y": "A"},
        },
    )

    plan = compile_workflow(spec, origin_version="10.1.0.178")

    assert plan.source_previews[0]["rows"] == 3
    assert len(plan.source_previews[0]["source_sha256"]) == 64
    assert [stage.id for stage in plan.stages][:4] == [
        "preflight",
        "start",
        "prepare_copy",
        "import:curve",
    ]
    assert any(item["kind"] == "worksheet" for item in plan.expected_objects)
    assert any(item["kind"] == "analysis_operation" for item in plan.expected_objects)
    mutation_keys = [stage.idempotency_key for stage in plan.stages if stage.mutation]
    assert all(mutation_keys)
    assert len(mutation_keys) == len(set(mutation_keys))


def test_planner_blocks_ambiguous_header_and_existing_output(tmp_path: Path):
    source = tmp_path / "ambiguous.csv"
    source.write_text("Name,Value\nLabel,Reading\nA,1\nB,2\n", encoding="utf-8")
    output = tmp_path / "existing.opju"
    output.write_bytes(b"existing")
    spec = WorkflowSpec.model_validate(
        {
            "intent": "import_and_plot",
            "sources": [{"id": "source", "path": str(source)}],
            "outputs": {"project_path": str(output)},
        }
    )

    plan = compile_workflow(spec, origin_version=None)

    assert any(item["code"] == "HEADER_AMBIGUOUS" for item in plan.blockers)
    assert any(item["code"] == "OUTPUT_EXISTS" for item in plan.blockers)


def test_idempotency_keys_are_stable_for_same_plan(tmp_path: Path):
    spec = _derivative_spec(tmp_path)

    first = compile_workflow(spec, origin_version=None)
    second = compile_workflow(spec, origin_version=None)

    assert [stage.idempotency_key for stage in first.stages] == [
        stage.idempotency_key for stage in second.stages
    ]
