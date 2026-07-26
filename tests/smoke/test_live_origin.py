import os
import time

import psutil
import pytest
from openpyxl import Workbook

from origin_com_automation.com.origin_api import OriginController, is_origin_process_name


def origin_pids():
    return {
        int(process.info["pid"])
        for process in psutil.process_iter(["pid", "name"])
        if is_origin_process_name(str(process.info.get("name", "")))
    }


@pytest.mark.smoke
@pytest.mark.integration
def test_owned_origin_end_to_end(tmp_path):
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
        assert started.origin_version

        mixed_path = tmp_path / "wse2-mixed.xlsx"
        workbook = Workbook()
        mixed_sheet = workbook.active
        mixed_sheet.title = "p-WSe2-only"
        mixed_sheet.append(
            ["Lch", "Rc", "Ion", "on/off ratio", "Units", "Source", "Year", "Type", "Label", "Notes"]
        )
        for index in range(26):
            ion = 2260 if index == 0 else 950 if index == 25 else 2200 - index * 45
            rc = 0.041 if index == 0 else "NA" if index == 1 else index / 10
            ratio = "≈1" if index == 0 else 1.0e5 + index
            mixed_sheet.append(
                [20 + index, rc, ion, ratio, "μA/μm", f"paper-{index}", 2024, "pFET", f"P{index}", None]
            )
        workbook.save(mixed_path)

        mixed_import = controller.import_data(
            file_path=str(mixed_path),
            worksheet_name="WSe2Mixed",
            sheet_name="p-WSe2-only",
            has_header=True,
        )
        assert mixed_import.success, mixed_import.to_dict()
        assert mixed_import.data["rows"] == 26
        profiles = {item["label"]: item for item in mixed_import.data["column_profiles"]}
        assert profiles["Ion"]["source"]["numeric_count"] == 26
        assert profiles["Ion"]["destination"]["numeric_count"] == 26
        assert profiles["Ion"]["first_value"] == 2260
        assert profiles["Ion"]["last_value"] == 950
        assert profiles["Rc"]["data_format"] == 9
        mixed_ref = mixed_import.data["worksheet_ref"]

        ion_write = controller.write_worksheet(mixed_ref, [[2261]], row=0, column=2)
        assert ion_write.success, ion_write.to_dict()
        assert ion_write.data["readback_verified"] is True
        ion_restore = controller.write_worksheet(mixed_ref, [[2260]], row=0, column=2)
        assert ion_restore.success, ion_restore.to_dict()

        appended = controller.write_worksheet(
            mixed_ref,
            [[3.14, "alpha", 0.041], [2.72, "beta", "NA"]],
            row=0,
            column=10,
        )
        assert appended.success, appended.to_dict()
        assert appended.data["column_data_formats"] == [0, 1, 9]
        appended_read = controller.read_worksheet(
            mixed_ref, r1=0, c1=10, r2=1, c2=12, data_format="auto"
        )
        assert appended_read.success, appended_read.to_dict()
        assert appended_read.data["values"] == [[3.14, "alpha", 0.041], [2.72, "beta", "NA"]]

        data_path = tmp_path / "smoke.csv"
        data_path.write_text("x,y,y2\n0,0,0\n1,1,1\n2,4,8\n3,9,27\n", encoding="ascii")
        imported = controller.import_data(file_path=str(data_path), worksheet_name="SmokeData")
        assert imported.success, imported.to_dict()

        read_back = controller.read_worksheet("SmokeData", r1=0, c1=0, r2=3, c2=2)
        assert read_back.success, read_back.to_dict()
        assert len(read_back.data["values"]) == 4
        assert all(len(row) == 3 for row in read_back.data["values"])

        analyzed = controller.run_analysis(
            worksheet_name="SmokeData",
            method="polynomial_fit",
            x_column="A",
            y_column="B",
            options={"degree": 2},
            row_start=0,
            row_end=3,
            filters=[{"column": "x", "operator": "ge", "value": 0}],
            row_order="as_is",
        )
        assert analyzed.success, analyzed.to_dict()
        assert analyzed.data["result"]["r_squared"] > 0.999

        plotted = controller.create_plot(
            worksheet_name="SmokeData",
            graph_type="scatter",
            x_column=0,
            y_columns=[1],
            graph_name="SmokeGraph",
        )
        assert plotted.success, plotted.to_dict()

        configured = controller.configure_graph(
            graph_name=plotted.data["graph_id"],
            options={
                "x_min": 0,
                "x_max": 3,
                "x_tick_step": 1,
                "x_title": "x",
                "y_title": "y",
                "legend": True,
                "plot_styles": [
                    {"plot_index": 1, "color_index": 4, "line_connection": "none"}
                ],
                "data_binding": {
                    "worksheet_name": "SmokeData",
                    "x_column": "A",
                    "y_columns": ["C"],
                    "plot_type": "scatter",
                },
            },
        )
        assert configured.success, configured.to_dict()

        multi = controller.create_plot(
            worksheet_name="SmokeData",
            graph_type="multi_layer",
            x_column="A",
            y_columns=["B", "C"],
            graph_name="SmokeMulti",
        )
        assert multi.success, multi.to_dict()
        assert multi.data["layers_created"] == 2

        audit = controller.list_objects()
        assert audit.success, audit.to_dict()
        page_names = [page["name"] for page in audit.data["pages"]]
        assert len(page_names) == len(set(page_names))
        smoke_sheet = next(item for item in audit.data["worksheets"] if item["page_name"] == "SmokeData")
        assert smoke_sheet["id"].startswith("[SmokeData]")
        assert len(smoke_sheet["columns"]) >= 3
        assert [item["long_name"] for item in smoke_sheet["columns"][:3]] == ["x", "y", "y2"]
        graph_sources = [
            item
            for item in audit.data["data_sources"]
            if item["page_name"] in {plotted.data["graph_name"], multi.data["graph_name"]}
            and item["collection"] == "DataPlots"
        ]
        assert graph_sources
        smoke_graph_sources = [
            item for item in graph_sources if item["page_name"] == plotted.data["graph_name"]
        ]
        assert [item["name"] for item in smoke_graph_sources] == ["SmokeData_C"]

        image_path = tmp_path / "smoke.png"
        image_path.write_bytes(b"existing")
        exported = controller.export_graph(
            graph_name=plotted.data["graph_id"],
            output_path=str(image_path),
            export_format="png",
            overwrite="rename",
        )
        assert exported.success, exported.to_dict()
        exported_path = exported.artifacts[0].path
        assert os.path.abspath(exported_path) != os.path.abspath(image_path)
        assert os.path.isfile(exported_path) and os.path.getsize(exported_path) > 0
        assert image_path.read_bytes() == b"existing"

        project_path = tmp_path / "smoke.opju"
        saved = controller.save_project_copy(target_path=str(project_path))
        assert saved.success, saved.to_dict()
        assert project_path.is_file() and project_path.stat().st_size > 0
    finally:
        stopped = controller.shutdown()
        assert stopped.success, stopped.to_dict()
        for _ in range(50):
            if not (origin_pids() - before):
                break
            time.sleep(0.2)
        assert not (origin_pids() - before)
        assert before.issubset(origin_pids())
