import pytest
from pydantic import ValidationError

from origin_com_automation.contracts import ResultEnvelope
from origin_com_automation.workflows.executor import execute_figure
from origin_com_automation.workflows.figurespec import FigureSpec, compile_figure_spec, figure_spec_digest
from origin_com_automation.workflows.adapters import figure_to_workflow_spec


def minimal_spec(**changes):
    data = {
        "route": "data_to_project",
        "input": {"path": "C:/data/input.csv", "worksheet_ref": "[Book1]Data"},
        "plots": [
            {
                "id": "main",
                "graph_type": "scatter",
                "roles": {"worksheet": "[Book1]Data", "x": "A", "y": "B"},
                "graph_name": "MainGraph",
            }
        ],
        "outputs": {"project_path": "C:/out/result.opju", "overwrite": "error"},
        "qa": {"critical_columns": ["A", "B"], "minimum_rows": 2},
    }
    data.update(changes)
    return FigureSpec.model_validate(data)


def test_figurespec_digest_is_stable_and_changes_with_scientific_field():
    first = minimal_spec()
    same = minimal_spec()
    changed = minimal_spec(
        plots=[
            {
                "id": "main",
                "graph_type": "line",
                "roles": {"worksheet": "[Book1]Data", "x": "A", "y": "B"},
                "graph_name": "MainGraph",
            }
        ]
    )
    assert figure_spec_digest(first) == figure_spec_digest(same)
    assert figure_spec_digest(first) != figure_spec_digest(changed)


def test_figurespec_digest_changes_with_source_and_analysis_execution_modes():
    native = minimal_spec(
        analyses=[
            {
                "id": "fit",
                "method": "linear_fit",
                "worksheet_ref": "[Book1]Data",
                "x_column": "A",
                "y_column": "B",
            }
        ]
    )
    snapshot = minimal_spec(
        input={
            "path": "C:/data/input.csv",
            "worksheet_ref": "[Book1]Data",
            "source_mode": "snapshot",
        },
        analyses=[
            {
                "id": "fit",
                "method": "linear_fit",
                "worksheet_ref": "[Book1]Data",
                "x_column": "A",
                "y_column": "B",
                "backend": "python",
                "create_operation": False,
                "recalculate_mode": "none",
            }
        ],
    )

    assert native.input.source_mode == "linked"
    assert native.analyses[0].backend == "origin_native"
    assert native.analyses[0].create_operation is True
    assert native.analyses[0].recalculate_mode == "auto"
    assert figure_spec_digest(native) != figure_spec_digest(snapshot)


def test_figurespec_adapter_uses_one_workflow_contract_for_data_and_restyle_routes(tmp_path):
    source = tmp_path / "input.csv"
    source.write_text("x,y\n1,2\n", encoding="utf-8")
    data_spec = minimal_spec(
        input={"path": str(source), "worksheet_ref": "[Book1]Data"},
        outputs={"project_path": str(tmp_path / "data.opju")},
    )
    workflow = figure_to_workflow_spec(data_spec)
    assert workflow.intent == "custom"
    assert workflow.sources[0].import_mode == "linked"
    assert workflow.execution.checkpoint_policy == "none"
    assert workflow.plots[0].roles["worksheet"] == "[Book1]Data"

    project = tmp_path / "input.opju"
    project.write_bytes(b"Origin project")
    restyle = minimal_spec(
        route="restyle_project",
        input={"path": str(project), "worksheet_ref": "[Book1]Data"},
        outputs={"project_path": str(tmp_path / "restyled.opju")},
    )
    restyle_workflow = figure_to_workflow_spec(restyle)
    assert restyle_workflow.intent == "custom"
    assert restyle_workflow.sources[0].import_mode == "project"
    assert restyle_workflow.sources[0].path == str(project.resolve())


def test_figurespec_analysis_execution_modes_are_not_duplicated_inside_options():
    with pytest.raises(ValidationError, match="reserved"):
        minimal_spec(
            analyses=[
                {
                    "id": "fit",
                    "method": "linear_fit",
                    "worksheet_ref": "[Book1]Data",
                    "x_column": "A",
                    "y_column": "B",
                    "options": {"backend": "python"},
                }
            ]
        )


def test_figurespec_rejects_unknown_fields_and_duplicate_ids():
    with pytest.raises(ValidationError, match="Extra inputs"):
        minimal_spec(typo=True)
    with pytest.raises(ValueError, match="plot ids must be unique"):
        minimal_spec(
            plots=[
                {"id": "same", "graph_type": "line", "roles": {"worksheet": "W", "x": "A", "y": "B"}},
                {"id": "same", "graph_type": "scatter", "roles": {"worksheet": "W", "x": "A", "y": "B"}},
            ]
        )


def test_compile_marks_unverified_graph_ineligible_without_opt_in(tmp_path):
    source = tmp_path / "input.csv"
    source.write_text("x,y\n1,2\n", encoding="utf-8")
    spec = minimal_spec(
        input={"path": str(source), "worksheet_ref": "[Book1]Data"},
        plots=[
            {
                "id": "polar",
                "graph_type": "polar",
                "roles": {"worksheet": "[Book1]Data", "angle": "A", "radius": "B"},
            }
        ],
    )
    plan = compile_figure_spec(spec, origin_version="10.1.0.178")
    assert plan["executor_executable"] is False
    assert any("supported-unverified" in item for item in plan["blockers"])
    assert plan["stages"][0]["id"] == "preflight"


def test_compile_data_route_checks_input_and_output_collision(tmp_path):
    source = tmp_path / "input.csv"
    source.write_text("x,y\n1,2\n", encoding="utf-8")
    output = tmp_path / "result.opju"
    output.write_bytes(b"existing")
    spec = minimal_spec(
        input={"path": str(source), "worksheet_ref": "[Book1]Data"},
        outputs={"project_path": str(output), "overwrite": "error"},
    )
    plan = compile_figure_spec(spec, origin_version="10.1.0.178")
    assert plan["executor_executable"] is False
    assert any("already exists" in item for item in plan["blockers"])


def test_compile_exposes_connector_and_native_operation_stages(tmp_path):
    source = tmp_path / "input.csv"
    source.write_text("x,y\n1,2\n", encoding="utf-8")
    spec = minimal_spec(
        input={"path": str(source), "worksheet_ref": "[Book1]Data"},
        analyses=[
            {
                "id": "fit",
                "method": "linear_fit",
                "worksheet_ref": "[Book1]Data",
                "x_column": "A",
                "y_column": "B",
            }
        ],
        outputs={"project_path": str(tmp_path / "result.opju")},
    )

    plan = compile_figure_spec(spec, origin_version="10.1.0.178")

    assert plan["executor_executable"] is True
    stage_ids = [stage["id"] for stage in plan["stages"]]
    assert "connector" in stage_ids
    assert "native_operation" in stage_ids
    assert plan["execution_modes"] == {
        "source_mode": "linked",
        "analysis_backends": ["origin_native"],
        "native_operation_count": 1,
    }


class WorkflowController:
    origin_version = "10.1.0.178"

    def __init__(self):
        self.calls = []

    def _ok(self, name, **kwargs):
        self.calls.append((name, kwargs))
        return ResultEnvelope.ok(kwargs)

    def start(self, **kwargs):
        return self._ok("start", **kwargs)

    def import_data(self, **kwargs):
        return self._ok("import_data", **kwargs)

    def open_project(self, **kwargs):
        return self._ok("open_project", **kwargs)

    def run_analysis(self, **kwargs):
        return self._ok(
            "run_analysis",
            backend="origin_native",
            native_operation_created=True,
            editable_in_origin=True,
            operation_ref="op://fitlr/123456abcdef",
            outputs={"oy": "[Fit]Result!A:B"},
            **kwargs,
        )

    def create_graph(self, **kwargs):
        return self._ok("create_graph", **kwargs)

    def save_project_copy(self, **kwargs):
        return self._ok("save_project_copy", **kwargs)

    def export_graph(self, **kwargs):
        return self._ok("export_graph", **kwargs)

    def read_worksheet(self, name, **kwargs):
        self.calls.append(("read_worksheet", {"name": name, **kwargs}))
        return ResultEnvelope.ok({"values": [[1, 2], [3, 4]]})

    def shutdown(self):
        return self._ok("shutdown")


class Context:
    def __init__(self):
        self.stages = []
        self.completed = []
        self.failed = []

    def stage(self, value, *, mutation=False):
        self.stages.append((value, mutation))

    def complete_stage(self, *, actual=None):
        self.completed.append(actual)

    def fail_stage(self, error_code, error_message, *, actual=None):
        self.failed.append((error_code, error_message, actual))


def test_execute_figure_follows_compiled_key_path_and_always_shuts_down(tmp_path):
    source = tmp_path / "input.csv"
    source.write_text("x,y\n1,2\n3,4\n", encoding="utf-8")
    spec = minimal_spec(
        input={"path": str(source), "worksheet_ref": "[Book1]Data"},
        outputs={"project_path": str(tmp_path / "result.opju"), "overwrite": "error"},
    )
    controller = WorkflowController()
    context = Context()
    result = execute_figure(
        controller,
        spec,
        expected_digest=figure_spec_digest(spec),
        context=context,
    )
    assert result["success"] is True
    assert [name for name, _ in controller.calls] == [
        "start", "import_data", "create_graph", "save_project_copy", "read_worksheet", "shutdown"
    ]
    assert result["completed_stages"][-1] == "shutdown"
    assert context.completed


def test_execute_figure_forwards_linked_and_native_defaults(tmp_path):
    source = tmp_path / "input.csv"
    source.write_text("x,y\n1,2\n3,4\n", encoding="utf-8")
    spec = minimal_spec(
        input={"path": str(source), "worksheet_ref": "[Book1]Data"},
        analyses=[
            {
                "id": "fit",
                "method": "linear_fit",
                "worksheet_ref": "[Book1]Data",
                "x_column": "A",
                "y_column": "B",
            }
        ],
        outputs={"project_path": str(tmp_path / "result.opju")},
    )
    controller = WorkflowController()

    context = Context()
    result = execute_figure(
        controller,
        spec,
        expected_digest=figure_spec_digest(spec),
        context=context,
    )

    assert result["success"] is True
    imported = next(kwargs for name, kwargs in controller.calls if name == "import_data")
    analyzed = next(kwargs for name, kwargs in controller.calls if name == "run_analysis")
    assert imported["source_mode"] == "linked"
    assert analyzed["options"] == {
        "backend": "origin_native",
        "create_operation": True,
        "recalculate_mode": "auto",
    }
    assert "connector" in result["completed_stages"]
    assert "native_operation" in result["completed_stages"]


def test_execute_figure_stops_after_first_failed_stage(tmp_path):
    source = tmp_path / "input.csv"
    source.write_text("x,y\n1,2\n", encoding="utf-8")
    spec = minimal_spec(
        input={"path": str(source), "worksheet_ref": "[Book1]Data"},
        outputs={"project_path": str(tmp_path / "result.opju"), "overwrite": "error"},
    )

    class FailingController(WorkflowController):
        def create_graph(self, **kwargs):
            self.calls.append(("create_graph", kwargs))
            return ResultEnvelope.fail("PLOT_FAILED", "plot failed")

    controller = FailingController()
    context = Context()
    result = execute_figure(
        controller,
        spec,
        expected_digest=figure_spec_digest(spec),
        context=context,
    )
    assert result["success"] is False
    assert result["failed_stage"] == "plot"
    assert [name for name, _ in controller.calls] == ["start", "import_data", "create_graph", "shutdown"]
    assert context.failed == [("PLOT_FAILED", "plot failed", None)]
