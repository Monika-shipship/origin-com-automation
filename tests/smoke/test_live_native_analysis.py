import os
import time

import psutil
import pytest

from origin_com_automation.com.origin_api import OriginController, is_origin_process_name
from origin_com_automation.native.common import OutputRef, RangeRef


def origin_pids() -> set[int]:
    return {
        int(process.info["pid"])
        for process in psutil.process_iter(["pid", "name"])
        if is_origin_process_name(str(process.info.get("name", "")))
    }


@pytest.mark.smoke
@pytest.mark.integration
def test_live_native_fit_operation_recalculates(tmp_path):
    if os.getenv("ORIGIN_LIVE_SMOKE") != "1":
        pytest.skip("set ORIGIN_LIVE_SMOKE=1 to activate Origin COM")
    from origin_com_automation.com.discovery import discover_registrations

    if not any(item.available for item in discover_registrations()):
        pytest.skip("no registered Origin COM server was detected")
    before = origin_pids()
    if before and os.getenv("ORIGIN_ALLOW_EXISTING") != "1":
        pytest.skip("an Origin process is already running; live smoke will not risk attaching")

    controller = OriginController()
    try:
        started = controller.start(progid="Origin.Application", visible=False, attach=False)
        assert started.success, started.to_dict()
        assert started.data["owned"] is True

        source = tmp_path / "native-fit.csv"
        source.write_text("x,y\n0,1\n1,3\n2,5\n3,7\n", encoding="ascii")
        imported = controller.import_data(
            file_path=str(source), worksheet_name="NativeFit", has_header=True
        )
        assert imported.success, imported.to_dict()
        worksheet_ref = imported.data["worksheet_ref"]

        created = controller.run_xfunction(
            name="fitlr",
            parameters={"iy": RangeRef(f"{worksheet_ref}!(A,B)")},
            outputs={"oy": OutputRef("<new>")},
            create_operation=True,
            recalculate_mode="manual",
        )
        assert created.success, created.to_dict()
        assert created.data["outputs"]["oy"] == f"{worksheet_ref}!(C,D)"

        fetched = controller.get_analysis_operation(
            operation_ref=created.data["operation_ref"]
        )
        assert fetched.success, fetched.to_dict()
        assert fetched.data["status"] == "available"
        assert fetched.data["native_query_confirmed"] is True

        before_fit = controller.read_worksheet(
            worksheet_ref, r1=0, c1=2, r2=3, c2=3, data_format="numeric"
        )
        assert before_fit.success, before_fit.to_dict()
        before_values = before_fit.data["values"]

        changed = controller.write_worksheet(worksheet_ref, [[13.0]], row=3, column=1)
        assert changed.success, changed.to_dict()
        recalculated = controller.recalculate_analysis(
            operation_ref=created.data["operation_ref"], wait=True
        )
        assert recalculated.success, recalculated.to_dict()
        assert recalculated.data["recalculated"] is True

        after_fit = controller.read_worksheet(
            worksheet_ref, r1=0, c1=2, r2=3, c2=3, data_format="numeric"
        )
        assert after_fit.success, after_fit.to_dict()
        assert after_fit.data["values"] != before_values
    finally:
        stopped = controller.shutdown()
        assert stopped.success, stopped.to_dict()
        for _ in range(50):
            if not (origin_pids() - before):
                break
            time.sleep(0.2)
        assert not (origin_pids() - before)
        assert before.issubset(origin_pids())
