from __future__ import annotations

import json
from pathlib import Path

import pytest

from origin_com_automation.contracts import ResultEnvelope
from origin_com_automation.workflows.engine import WorkflowEngine, WorkflowExecutionError
from origin_com_automation.workflows.spec import WorkflowSpec, workflow_spec_digest
from origin_com_automation.workflows.tasks import TaskManager


def workflow_spec(tmp_path: Path, **changes) -> WorkflowSpec:
    source = tmp_path / "input.csv"
    source.write_text("x,y\n1,2\n3,4\n", encoding="utf-8")
    payload = {
        "intent": "fit_and_plot",
        "sources": [{"id": "data", "path": str(source), "worksheet_ref": "[Data]Sheet1"}],
        "scientific_contract": {
            "branch": "all",
            "fit_method": "ordinary_least_squares",
            "input_units": {"x": "V", "y": "A"},
        },
        "analyses": [{
            "id": "fit",
            "method": "linear_fit",
            "worksheet_ref": "[Data]Sheet1",
            "x_column": "A",
            "y_columns": ["B"],
        }],
        "plots": [{
            "id": "main",
            "graph_type": "scatter",
            "roles": {"worksheet": "[Data]Sheet1", "x": "A", "y": ["B"]},
            "graph_name": "MainGraph",
        }],
        "outputs": {"project_path": str(tmp_path / "result.opju")},
        "qa": {"minimum_rows": 2, "require_connector": True},
    }
    payload.update(changes)
    return WorkflowSpec.model_validate(payload)


class FakeController:
    origin_version = "10.1.0.178"

    def __init__(self, *, fail_stage: str | None = None):
        self.calls: list[tuple[str, dict]] = []
        self.fail_stage = fail_stage

    def _result(self, operation: str, data: dict | None = None, **kwargs):
        self.calls.append((operation, kwargs))
        if self.fail_stage == operation:
            return ResultEnvelope.fail("FAKE_FAILURE", f"{operation} failed")
        return ResultEnvelope.ok(data or kwargs, origin_version=self.origin_version)

    def start(self, **kwargs):
        return self._result("start", {"session_id": "owned-1", "owned": True, "pid": 1234}, **kwargs)

    def import_data(self, **kwargs):
        return self._result(
            "import_data",
            {"worksheet_ref": "[Data]input", "rows": 2, "non_empty_counts": [2, 2]},
            **kwargs,
        )

    def read_worksheet(self, name, **kwargs):
        return self._result("read_worksheet", {"worksheet_ref": name, "values": [[1, 2], [3, 4]], "rows": 2}, name=name, **kwargs)

    def run_analysis(self, **kwargs):
        return self._result("run_analysis", {"operation_ref": "operation:fit", "recalculate_mode": "auto"}, **kwargs)

    def create_graph(self, **kwargs):
        return self._result("create_graph", {"graph_name": "MainGraph", "graph_ref": "graph:main"}, **kwargs)

    def save_project_copy(self, **kwargs):
        target = Path(kwargs["target_path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"Origin project checkpoint")
        return self._result("save_project_copy", {"path": str(target), "size": target.stat().st_size}, **kwargs)

    def export_graph(self, **kwargs):
        return self._result("export_graph", {"path": kwargs["output_path"]}, **kwargs)

    def list_objects(self):
        return self._result("list_objects", {"graphs": [{"name": "MainGraph"}]})

    def open_project(self, **kwargs):
        return self._result("open_project", {"path": kwargs["source_path"]}, **kwargs)

    def shutdown(self):
        return self._result("shutdown", {"shutdown": True, "owned": True})


def test_execute_rejects_digest_drift_and_unresolved_decisions(tmp_path):
    spec = workflow_spec(tmp_path)
    engine = WorkflowEngine(lambda: FakeController(), task_manager=TaskManager())
    with pytest.raises(WorkflowExecutionError, match="digest"):
        engine.execute(spec, expected_digest="wrong", idempotency_key="run-1")

    unresolved = workflow_spec(tmp_path, scientific_contract={"branch": "all"})
    with pytest.raises(WorkflowExecutionError, match="required scientific decisions"):
        engine.execute(
            unresolved,
            expected_digest=workflow_spec_digest(unresolved),
            idempotency_key="run-2",
        )
    engine.close()


def test_execute_calls_public_controller_methods_in_order_and_verifies_mutations(tmp_path):
    spec = workflow_spec(tmp_path)
    controller = FakeController()
    engine = WorkflowEngine(lambda: controller, task_manager=TaskManager())
    result = engine.execute(
        spec,
        expected_digest=workflow_spec_digest(spec),
        idempotency_key="approved-1",
    )

    assert result["success"] is True
    names = [name for name, _ in controller.calls]
    assert names == [
        "start",
        "import_data",
        "run_analysis",
        "create_graph",
        "save_project_copy",
        "shutdown",
    ]
    started_args = next(kwargs for name, kwargs in controller.calls if name == "start")
    assert started_args == {"visible": False, "attach": False, "exclusive": False}
    imported_args = next(kwargs for name, kwargs in controller.calls if name == "import_data")
    assert imported_args["worksheet_name"] == "Data"
    analysis_args = next(kwargs for name, kwargs in controller.calls if name == "run_analysis")
    assert analysis_args["worksheet_name"] == "[Data]input"
    graph_args = next(kwargs for name, kwargs in controller.calls if name == "create_graph")
    assert graph_args["roles"]["worksheet"] == "[Data]input"
    assert names.count("save_project_copy") == 1
    assert "read_worksheet" not in names
    assert "list_objects" not in names
    assert result["objects"]["analysis:fit"]["operation_ref"] == "operation:fit"
    assert result["objects"]["graph:main"]["graph_ref"] == "graph:main"
    assert Path(result["ledger_path"]).is_file()
    ledger = json.loads(Path(result["ledger_path"]).read_text(encoding="utf-8"))
    assert ledger["digest"] == workflow_spec_digest(spec)
    assert all(item["state"] == "completed" for item in ledger["stages"])
    assert ledger["checkpoints"] == []
    manifest_paths = [item["path"] for item in result["artifacts"] if item["kind"].startswith("workflow_manifest")]
    assert manifest_paths == []
    engine.close()


def test_resume_skips_completed_mutations_and_opens_last_checkpoint(tmp_path):
    spec = workflow_spec(tmp_path, execution={"checkpoint_policy": "milestone"})
    first = FakeController(fail_stage="create_graph")
    engine = WorkflowEngine(lambda: first, task_manager=TaskManager())
    failed = engine.execute(
        spec,
        expected_digest=workflow_spec_digest(spec),
        idempotency_key="resume-me",
    )
    assert failed["success"] is False
    assert failed["failed_stage"] == "plot:main"
    assert [name for name, _ in first.calls].count("run_analysis") == 1

    second = FakeController()
    engine.controller_factory = lambda: second
    resumed = engine.resume(
        spec,
        expected_digest=workflow_spec_digest(spec),
        idempotency_key="resume-me",
    )
    assert resumed["success"] is True
    names = [name for name, _ in second.calls]
    assert names[:2] == ["start", "open_project"]
    assert "import_data" not in names
    assert "run_analysis" not in names
    assert names.count("create_graph") == 1
    assert names[-1] == "shutdown"
    engine.close()


def test_milestone_recovery_creates_only_one_checkpoint_after_analysis(tmp_path):
    spec = workflow_spec(tmp_path, execution={"checkpoint_policy": "milestone"})
    controller = FakeController()
    engine = WorkflowEngine(lambda: controller, task_manager=TaskManager())

    result = engine.execute(
        spec,
        expected_digest=workflow_spec_digest(spec),
        idempotency_key="one-milestone",
    )

    assert result["success"] is True
    checkpoint_calls = [
        kwargs
        for name, kwargs in controller.calls
        if name == "save_project_copy" and "checkpoint-" in kwargs["target_path"]
    ]
    assert len(checkpoint_calls) == 1
    assert "analysis" in checkpoint_calls[0]["target_path"]
    final_saves = [
        kwargs
        for name, kwargs in controller.calls
        if name == "save_project_copy" and kwargs["target_path"] == str(tmp_path / "result.opju")
    ]
    assert len(final_saves) == 1
    assert len(result["checkpoints"]) == 1
    engine.close()


def test_engine_forwards_scientific_native_derivative_contract(tmp_path):
    spec = workflow_spec(
        tmp_path,
        intent="curve_analysis",
        scientific_contract={
            "branch": "all",
            "derivative_method": "differentiate",
            "derivative_order": 2,
            "input_units": {"x": "V", "y": "A"},
        },
        analyses=[{
            "id": "derivative",
            "method": "derivative",
            "worksheet_ref": "[Data]Sheet1",
            "x_column": "A",
            "y_columns": ["B"],
        }],
        plots=[],
    )
    controller = FakeController()
    engine = WorkflowEngine(lambda: controller, task_manager=TaskManager())
    result = engine.execute(
        spec,
        expected_digest=workflow_spec_digest(spec),
        idempotency_key="native-derivative",
    )
    assert result["success"] is True
    options = next(kwargs["options"] for name, kwargs in controller.calls if name == "run_analysis")
    assert options["derivative_method"] == "differentiate"
    assert options["order"] == 2
    assert options["backend"] == "origin_native"
    engine.close()
