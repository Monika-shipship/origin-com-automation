import os
import time

import psutil
import pytest
from openpyxl import Workbook

from origin_com_automation.com.origin_api import OriginController, is_origin_process_name
from origin_com_automation.native.operations import build_get_operation_command


def origin_pids() -> set[int]:
    return {
        int(process.info["pid"])
        for process in psutil.process_iter(["pid", "name"])
        if is_origin_process_name(str(process.info.get("name", "")))
    }


def require_live_origin() -> set[int]:
    if os.getenv("ORIGIN_LIVE_SMOKE") != "1":
        pytest.skip("set ORIGIN_LIVE_SMOKE=1 to activate Origin COM")
    from origin_com_automation.com.discovery import discover_registrations

    if not any(item.available for item in discover_registrations()):
        pytest.skip("no registered Origin COM server was detected")
    before = origin_pids()
    if before and os.getenv("ORIGIN_ALLOW_EXISTING") != "1":
        pytest.skip("an Origin process is already running; live smoke will not risk attaching")
    return before


def assert_owned_exit(before: set[int]) -> None:
    for _ in range(100):
        if not (origin_pids() - before):
            break
        time.sleep(0.2)
    assert not (origin_pids() - before)
    assert before.issubset(origin_pids())


@pytest.mark.smoke
@pytest.mark.integration
def test_live_linked_excel_selection_and_one_row_header(tmp_path):
    before = require_live_origin()
    source = tmp_path / "native-defaults.xlsx"
    workbook = Workbook()
    workbook.active.title = "Ignore"
    workbook.active.append(["wrong", "sheet"])
    target = workbook.create_sheet("Target")
    target.append(["x", "y"])
    target.append([1, 2])
    target.append([3, 4])
    workbook.save(source)

    controller = OriginController()
    try:
        started = controller.start(progid="Origin.Application", visible=False, attach=False)
        assert started.success, started.to_dict()
        imported = controller.import_data(
            file_path=str(source),
            worksheet_name="ExcelDefaults",
            sheet_name="Target",
            has_header=True,
        )
        assert imported.success, imported.to_dict()
        assert imported.data["source_mode"] == "linked"
        assert imported.data["connector"]["selection"] == "Target"
        worksheet_ref = imported.data["worksheet_ref"]

        objects = controller.list_objects()
        assert objects.success, objects.to_dict()
        worksheet = next(
            item for item in objects.data["worksheets"] if item["id"] == worksheet_ref
        )
        assert [column["long_name"] for column in worksheet["columns"][:2]] == [
            "x",
            "y",
        ]

        values = controller.read_worksheet(
            worksheet_ref, r1=0, c1=0, r2=1, c2=1, data_format="numeric"
        )
        assert values.success, values.to_dict()
        assert values.data["values"] == [[1.0, 2.0], [3.0, 4.0]]
    finally:
        stopped = controller.shutdown()
        assert stopped.success, stopped.to_dict()
    assert_owned_exit(before)


@pytest.mark.smoke
@pytest.mark.integration
def test_live_linked_formula_and_native_fit_persist(tmp_path):
    before = require_live_origin()
    source = tmp_path / "native-defaults.csv"
    source.write_text("x,y\n0,1\n1,3\n2,5\n3,7\n", encoding="ascii")
    project = tmp_path / "native-defaults.opju"
    reopened_copy = tmp_path / "native-defaults-reopened.opju"
    worksheet_ref = ""
    operation_range = ""

    controller = OriginController()
    try:
        started = controller.start(progid="Origin.Application", visible=False, attach=False)
        assert started.success, started.to_dict()
        assert started.data["owned"] is True

        imported = controller.import_data(
            file_path=str(source), worksheet_name="NativeDefaults", has_header=True
        )
        assert imported.success, imported.to_dict()
        assert imported.data["source_mode"] == "linked"
        assert imported.data["connector"]["connected"] is True
        worksheet_ref = imported.data["worksheet_ref"]

        formula = controller.set_column_formula(
            worksheet_ref=worksheet_ref,
            column="C",
            formula="col(A)*col(B)",
            recalculate_mode="auto",
        )
        assert formula.success, formula.to_dict()
        assert formula.data["formula"] == "col(A)*col(B)"
        assert formula.data["recalculate_value"] == 1
        assert formula.data["value_readback"] == [0.0, 3.0, 10.0, 21.0]

        source.write_text("x,y\n0,1\n1,3\n2,11\n3,7\n", encoding="ascii")
        refreshed = controller.manage_connector(
            action="refresh", worksheet_ref=worksheet_ref
        )
        assert refreshed.success, refreshed.to_dict()
        assert refreshed.data["auto_recalculation_flushed"] is True
        updated = controller.read_worksheet(
            worksheet_ref, r1=0, c1=0, r2=3, c2=2, data_format="numeric"
        )
        assert updated.success, updated.to_dict()
        assert updated.data["values"] == [
            [0.0, 1.0, 0.0],
            [1.0, 3.0, 3.0],
            [2.0, 11.0, 22.0],
            [3.0, 7.0, 21.0],
        ]

        before_unsupported = controller.list_objects()
        unsupported = controller.run_analysis(
            worksheet_name=worksheet_ref,
            method="smooth",
            x_column="A",
            y_column="B",
        )
        after_unsupported = controller.list_objects()
        assert before_unsupported.success and after_unsupported.success
        assert unsupported.success is False
        assert unsupported.error_code == "ORIGIN_NATIVE_METHOD_UNAVAILABLE"
        assert unsupported.data["python_fallback_attempted"] is False
        assert after_unsupported.data == before_unsupported.data

        fitted = controller.run_analysis(
            worksheet_name=worksheet_ref,
            method="linear_fit",
            x_column="A",
            y_column="B",
        )
        assert fitted.success, fitted.to_dict()
        assert fitted.data["backend"] == "origin_native"
        assert fitted.data["native_operation_created"] is True
        assert fitted.data["recalculate_mode"] == "auto"
        operation_range = next(iter(fitted.data["outputs"].values()))

        saved = controller.save_project_copy(target_path=str(project))
        assert saved.success, saved.to_dict()
        assert project.is_file() and project.stat().st_size > 100
    finally:
        stopped = controller.shutdown()
        assert stopped.success, stopped.to_dict()
    assert_owned_exit(before)

    reopened = OriginController()
    try:
        started = reopened.start(progid="Origin.Application", visible=False, attach=False)
        assert started.success, started.to_dict()
        opened = reopened.open_project(
            source_path=str(project), working_copy_path=str(reopened_copy)
        )
        assert opened.success, opened.to_dict()

        connector = reopened.manage_connector(action="info", worksheet_ref=worksheet_ref)
        assert connector.success, connector.to_dict()
        assert connector.data["connected"] is True
        assert connector.data["source"] == str(source.resolve())

        metadata = reopened.execute_labtalk(
            script=(
                f"range __codex_formula_col={worksheet_ref}!C; "
                "__codex_formula$=__codex_formula_col.formula$; "
                "__codex_formula_range$=__codex_formula_col.formulaRange$; "
                "__codex_svrm=__codex_formula_col.svrm;"
            ),
            result_string_variables=["__codex_formula", "__codex_formula_range"],
            result_numeric_variables=["__codex_svrm"],
        )
        assert metadata.success, metadata.to_dict()
        assert metadata.data["string_output"]["__codex_formula"] == "col(A)*col(B)"
        assert metadata.data["numeric_output"]["__codex_svrm"] == 1

        values = reopened.read_worksheet(
            worksheet_ref, r1=0, c1=0, r2=3, c2=2, data_format="numeric"
        )
        assert values.success, values.to_dict()
        assert values.data["values"][2] == [2.0, 11.0, 22.0]

        operation = reopened.execute_labtalk(
            script=build_get_operation_command(operation_range)
        )
        assert operation.success, operation.to_dict()
    finally:
        stopped = reopened.shutdown()
        assert stopped.success, stopped.to_dict()
    assert_owned_exit(before)
