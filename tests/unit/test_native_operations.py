import pytest

from origin_com_automation.com.origin_api import OriginController
from origin_com_automation.native.common import NativeValidationError, OutputRef, RangeRef
from origin_com_automation.native.operations import (
    AnalysisOperationRegistry,
    build_analysis_template_plan,
    build_get_operation_command,
    build_recalculate_operation_command,
    execute_analysis_template_plan,
    execute_xfunction_plan,
    normalize_operation_ref,
    read_analysis_operation,
    recalculate_operation,
)
from origin_com_automation.native.xfunctions import build_xfunction_plan


class NativeApp:
    Version = "10.1.0.178"

    def __init__(self):
        self.scripts = []
        self.execute_result = True
        self.lt_strings = {
            "fitlr.oy$": '[Book1]Data!(C"FitLR X",D"FitLR Y")',
        }

    def Execute(self, script):
        self.scripts.append(script)
        return self.execute_result

    def LTVar(self, name):
        raise AssertionError(f"unexpected LTVar read: {name}")

    def LTStr(self, name):
        return self.lt_strings.get(name, "")


class InlineWorker:
    def submit(self, fn, *, timeout=None):
        return fn()


def owned_controller(app):
    controller = OriginController(worker=InlineWorker())
    controller._app = app
    record = controller.sessions.register(
        progid="Origin.Application",
        pid=123,
        owned=True,
        visible=False,
    )
    controller._session_id = record.session_id
    controller._origin_version = app.Version
    return controller


def test_operation_refs_are_stable_and_normalized():
    ref = normalize_operation_ref("op://fitlr/abc123")
    assert ref == "op://fitlr/abc123"
    with pytest.raises(NativeValidationError, match="operation ref"):
        normalize_operation_ref('op://fitlr/a";')


def test_registry_tracks_plugin_created_operations_only():
    registry = AnalysisOperationRegistry()
    plan = build_xfunction_plan(
        "fitlr",
        {"iy": RangeRef("[Book1]Data!A:B")},
        outputs={"oy": OutputRef("[Book1]Fit!A:B")},
        create_operation=True,
        recalculate_mode="auto",
    )
    app = NativeApp()

    result = execute_xfunction_plan(app, plan, registry)

    assert result["operation_ref"] == plan.operation_ref
    operation = registry.get(plan.operation_ref)
    assert operation["xfunction"] == "fitlr"
    assert operation["recalculate_mode"] == "auto"
    assert operation["result_refs"] == {"oy": "[Book1]Fit!A:B"}


def test_dynamic_xfunction_output_is_resolved_before_operation_registration():
    registry = AnalysisOperationRegistry()
    plan = build_xfunction_plan(
        "fitlr",
        {"iy": RangeRef("[Book1]Data!(A,B)")},
        outputs={"oy": OutputRef("<new>")},
        create_operation=True,
        recalculate_mode="auto",
    )

    result = execute_xfunction_plan(NativeApp(), plan, registry)

    assert result["outputs"] == {"oy": "[Book1]Data!(C,D)"}
    operation = registry.get(plan.operation_ref)
    assert operation["operation_range"] == "[Book1]Data!(C,D)"
    assert operation["result_refs"] == {"oy": "[Book1]Data!(C,D)"}


def test_implicit_fitlr_output_is_discovered_for_operation_registration():
    registry = AnalysisOperationRegistry()
    plan = build_xfunction_plan(
        "fitlr",
        {"iy": RangeRef("[Book1]Data!(A,B)")},
        create_operation=True,
        recalculate_mode="auto",
    )

    result = execute_xfunction_plan(NativeApp(), plan, registry)

    assert result["outputs"] == {"oy": "[Book1]Data!(C,D)"}
    assert registry.get(plan.operation_ref)["operation_range"] == "[Book1]Data!(C,D)"


def test_operation_commands_reject_unsafe_ranges():
    assert build_get_operation_command("[Book1]Fit!A1") == (
        "op_change ir:=[Book1]Fit!A1 tr:=__codex_op_tree op:=get;"
    )
    assert build_recalculate_operation_command("[Book1]Fit!A1") == (
        "op_change ir:=[Book1]Fit!A1 tr:=__codex_op_tree op:=run;"
    )
    with pytest.raises(NativeValidationError, match="unsafe"):
        build_get_operation_command("[Book]1!A; del -all")


def test_read_and_recalculate_use_op_change_and_verify_state():
    app = NativeApp()
    registry = AnalysisOperationRegistry()
    registry.register(
        operation_ref="op://fitlr/abc123",
        xfunction="fitlr",
        operation_range="[Book1]Fit!A1",
        recalculate_mode="auto",
        result_refs={"oy": "[Book1]Fit!A:B"},
    )

    before = read_analysis_operation(app, "op://fitlr/abc123", registry)
    after = recalculate_operation(app, "op://fitlr/abc123", registry, wait=True)

    assert before["status"] == "available"
    assert before["native_query_confirmed"] is True
    assert after["recalculated"] is True
    assert app.scripts == [
        "op_change ir:=[Book1]Fit!A1 tr:=__codex_op_tree op:=get;",
        "op_change ir:=[Book1]Fit!A1 tr:=__codex_op_tree op:=run;",
        "op_change ir:=[Book1]Fit!A1 tr:=__codex_op_tree op:=get;",
    ]


def test_recalculation_readback_failure_is_not_reported_as_success():
    app = NativeApp()
    app.execute_result = False
    registry = AnalysisOperationRegistry()
    registry.register(
        operation_ref="op://fitlr/abc123",
        xfunction="fitlr",
        operation_range="[Book1]Fit!A1",
        recalculate_mode="manual",
        result_refs={},
    )

    with pytest.raises(NativeValidationError, match="did not confirm"):
        recalculate_operation(app, "op://fitlr/abc123", registry, wait=True)


def test_analysis_template_plans_validate_extension_and_overwrite(tmp_path):
    target = tmp_path / "analysis.ogwu"
    plan = build_analysis_template_plan(
        action="save",
        path=str(target),
        workbook_ref="[Book1]",
        overwrite=False,
    )
    assert plan.command == f'save -ik "{target.as_posix()}";'

    target.write_text("existing", encoding="utf-8")
    with pytest.raises(NativeValidationError, match="already exists"):
        build_analysis_template_plan(
            action="save",
            path=str(target),
            workbook_ref="[Book1]",
            overwrite=False,
        )
    with pytest.raises(NativeValidationError, match="extension"):
        build_analysis_template_plan(action="load", path=str(tmp_path / "bad.txt"))


def test_analysis_template_execution_checks_output_file(tmp_path):
    target = tmp_path / "analysis.ogwu"
    plan = build_analysis_template_plan(
        action="save",
        path=str(target),
        workbook_ref="[Book1]",
        overwrite=False,
    )
    app = NativeApp()

    with pytest.raises(NativeValidationError, match="was not created"):
        execute_analysis_template_plan(app, plan)


def test_controller_runs_and_lists_plugin_created_operation():
    app = NativeApp()
    controller = owned_controller(app)

    created = controller.run_xfunction(
        name="fitlr",
        parameters={"iy": RangeRef("[Book1]Data!A:B")},
        outputs={"oy": OutputRef("[Book1]Fit!A:B")},
        create_operation=True,
        recalculate_mode="auto",
    )
    listed = controller.list_analysis_operations()
    fetched = controller.get_analysis_operation(
        operation_ref=created.data["operation_ref"]
    )

    assert created.success is True
    assert listed.success is True
    assert len(listed.data["operations"]) == 1
    assert fetched.success is True
    assert fetched.data["status"] == "available"


def test_controller_recalculation_is_mutating_and_unretried():
    app = NativeApp()
    controller = owned_controller(app)
    created = controller.run_xfunction(
        name="fitlr",
        parameters={"iy": RangeRef("[Book1]Data!A:B")},
        outputs={"oy": OutputRef("[Book1]Fit!A:B")},
        create_operation=True,
        recalculate_mode="manual",
    )

    result = controller.recalculate_analysis(
        operation_ref=created.data["operation_ref"], wait=True
    )

    assert result.success is True
    assert result.data["recalculated"] is True


def test_controller_rejects_native_mutation_in_attached_session():
    app = NativeApp()
    controller = OriginController(worker=InlineWorker())
    controller._app = app
    record = controller.sessions.register(
        progid="Origin.ApplicationSI", pid=456, owned=False, visible=True
    )
    controller._session_id = record.session_id

    result = controller.run_xfunction(
        name="fitlr",
        parameters={"iy": RangeRef("[Book1]Data!A:B")},
    )

    assert result.success is False
    assert result.error_code == "ATTACHED_SESSION_PROTECTED"


def test_controller_returns_stable_validation_error_for_bad_native_request():
    controller = owned_controller(NativeApp())

    result = controller.run_xfunction(
        name="fitlr",
        parameters={"iy": "untyped range"},
    )

    assert result.success is False
    assert result.error_code == "NATIVE_VALIDATION_FAILED"


def test_controller_routes_verified_native_linear_fit_without_python_fallback():
    app = NativeApp()
    controller = owned_controller(app)

    result = controller.run_analysis(
        worksheet_name="[Book1]Data",
        method="linear_fit",
        x_column="A",
        y_column="B",
        options={
            "backend": "origin_native",
            "create_operation": True,
            "recalculate_mode": "auto",
        },
    )

    assert result.success is True
    assert result.data["backend"] == "origin_native"
    assert result.data["operation_ref"].startswith("op://fitlr/")
    assert app.scripts == [
        "fitlr -r 1 iy:=[Book1]Data!(A,B);"
    ]


def test_controller_rejects_unmapped_native_analysis_method():
    controller = owned_controller(NativeApp())

    result = controller.run_analysis(
        worksheet_name="[Book1]Data",
        method="pca",
        x_column="A",
        y_column="B",
        options={"backend": "origin_native"},
    )

    assert result.success is False
    assert result.error_code == "NATIVE_ANALYSIS_UNSUPPORTED"
