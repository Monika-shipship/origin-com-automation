from __future__ import annotations

from collections import Counter
from hashlib import sha256
import os
from pathlib import Path
import time

import psutil
import pytest

from origin_com_automation.com.origin_api import (
    OriginController,
    _collection_items,
    _resolve_graph_layer,
    _safe_attr,
    is_origin_process_name,
)


EXPECTED_CATEGORIES = {
    "1L": 12,
    "2L": 11,
    "other": 1,
    "Lch uncertain": 1,
    "this work": 1,
}

CATEGORY_STYLE = {
    "plot_index": 1,
    "worksheet_name": "[WSe2Benchmark]Data",
    "category_column": "I",
    "categories": {
        "1L": {"color": "#2878B5", "shape": "circle", "fill": "solid", "size": 10},
        "2L": {"color": "#E76F51", "shape": "square", "fill": "solid", "size": 10},
        "other": {
            "color": "#4D4D4D",
            "shape": "triangle_up",
            "fill": "solid",
            "size": 10,
        },
        "Lch uncertain": {
            "color": "#E9A400",
            "shape": "triangle_down",
            "fill": "solid",
            "size": 10,
        },
        "this work": {
            "color": "#2A9D55",
            "shape": "diamond",
            "fill": "solid",
            "size": 14,
        },
    },
}


def _origin_pids() -> set[int]:
    return {
        int(process.info["pid"])
        for process in psutil.process_iter(["pid", "name"])
        if is_origin_process_name(str(process.info.get("name", "")))
    }


def _file_digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _pixel_digest(path: Path) -> str:
    from PIL import Image

    with Image.open(path) as image:
        return sha256(image.convert("RGBA").tobytes()).hexdigest()


def _graph_options() -> dict:
    return {
        "x_scale": "log10",
        "y_scale": "log10",
        "x_min": 10,
        "x_max": 1000,
        "y_min": 100,
        "y_max": 3000,
        "data_binding": {
            "worksheet_name": "[WSe2Benchmark]Data",
            "x_column": "A",
            "y_columns": ["B"],
            "label_column": "C",
            "plot_type": "scatter",
        },
        "categorical_style": CATEGORY_STYLE,
        "legend": {
            "mode": "categorical",
            "source": "plot_style_mapping",
            "position": "top_right",
            "font_size": 9,
            "border": False,
            "background": "transparent",
            "replace_existing": True,
        },
    }


def _assert_project_structure(audit) -> dict:
    assert audit.success, audit.to_dict()
    assert [item["name"] for item in audit.data["workbooks"]] == ["WSe2Benchmark"]
    assert [item["name"] for item in audit.data["worksheets"]] == ["Data"]
    assert [item["name"] for item in audit.data["graphs"]] == ["Ion_vs_Lch"]
    sheet = audit.data["worksheets"][0]
    assert (sheet["rows"], sheet["cols"]) == (26, 13)
    plots = [
        item
        for item in audit.data["data_sources"]
        if item["collection"] == "DataPlots" and item["graph"] == "Ion_vs_Lch"
    ]
    assert len(plots) == 1
    plot = plots[0]
    assert {
        key: plot[key]
        for key in (
            "type",
            "source_workbook",
            "source_worksheet",
            "x_column",
            "x_dataset_name",
            "y_column",
            "y_dataset_name",
            "label_column",
            "label_dataset_name",
        )
    } == {
        "type": "DataPlot",
        "source_workbook": "WSe2Benchmark",
        "source_worksheet": "Data",
        "x_column": "A",
        "x_dataset_name": "WSe2Benchmark_A",
        "y_column": "B",
        "y_dataset_name": "WSe2Benchmark_B",
        "label_column": "C",
        "label_dataset_name": "WSe2Benchmark_C",
    }
    return plot


def _graph_object_snapshot(controller: OriginController) -> dict:
    def inspect() -> dict:
        app = controller._require_app()
        layer = _resolve_graph_layer(app, "Ion_vs_Lch")
        items = _collection_items(_safe_attr(layer, "GraphObjects"))
        return {
            "count": len(items),
            "names": [str(_safe_attr(item, "Name", "")) for item in items],
        }

    result = controller._submit(inspect)
    assert result.success, result.to_dict()
    return result.data


def _legend_text(controller: OriginController) -> str:
    result = controller.execute_labtalk(
        script=(
            'win -a Ion_vs_Lch;codex_legend_name$="%(Legend.name$)";'
            'codex_legend_text$="%(Legend.text$)";'
            'codex_legend_1$="%(1,m1,4)";codex_legend_2$="%(1,m2,4)";'
            'codex_legend_3$="%(1,m3,4)";codex_legend_4$="%(1,m4,4)";'
            'codex_legend_5$="%(1,m5,4)";'
        ),
        result_string_variables=[
            "codex_legend_name",
            "codex_legend_text",
            "codex_legend_1",
            "codex_legend_2",
            "codex_legend_3",
            "codex_legend_4",
            "codex_legend_5",
        ],
    )
    assert result.success, result.to_dict()
    text = result.data["string_output"]["codex_legend_text"]
    lines = [line.strip() for line in text.replace("%(CRLF)", "\n").splitlines() if line.strip()]
    assert len(lines) == 5
    assert {
        result.data["string_output"][f"codex_legend_{index}"] for index in range(1, 6)
    } == set(CATEGORY_STYLE["categories"])
    cleanup = controller.execute_labtalk(
        script=(
            "del -v codex_legend_name$;del -v codex_legend_text$;"
            "del -v codex_legend_1$;del -v codex_legend_2$;del -v codex_legend_3$;"
            "del -v codex_legend_4$;del -v codex_legend_5$;"
        )
    )
    assert cleanup.success, cleanup.to_dict()
    return text


def _assert_axis_state(controller: OriginController) -> None:
    result = controller.execute_labtalk(
        script=(
            "win -a Ion_vs_Lch;"
            "codex_x_type=layer.x.type;codex_y_type=layer.y.type;"
            "codex_x_from=layer.x.from;codex_x_to=layer.x.to;"
            "codex_y_from=layer.y.from;codex_y_to=layer.y.to;"
        ),
        result_numeric_variables=[
            "codex_x_type",
            "codex_y_type",
            "codex_x_from",
            "codex_x_to",
            "codex_y_from",
            "codex_y_to",
        ],
    )
    assert result.success, result.to_dict()
    assert result.data["numeric_output"] == {
        "codex_x_type": 2.0,
        "codex_y_type": 2.0,
        "codex_x_from": 10.0,
        "codex_x_to": 1000.0,
        "codex_y_from": 100.0,
        "codex_y_to": 3000.0,
    }


def _assert_last_point_style(controller: OriginController) -> None:
    result = controller.execute_labtalk(
        script=(
            "win -a Ion_vs_Lch;"
            "get WSe2Benchmark_B 26 -k codex_shape;"
            "get WSe2Benchmark_B 26 -kf codex_fill;"
            "get WSe2Benchmark_B 26 -z codex_size;"
        ),
        result_numeric_variables=["codex_shape", "codex_fill", "codex_size"],
    )
    assert result.success, result.to_dict()
    assert result.data["numeric_output"] == {
        "codex_shape": 5.0,
        "codex_fill": 0.0,
        "codex_size": 14.0,
    }


def _assert_marker_colors(path: Path) -> None:
    from PIL import Image

    targets = [
        tuple(int(color[index : index + 2], 16) for index in (1, 3, 5))
        for color in ("#2878B5", "#E76F51", "#4D4D4D", "#E9A400", "#2A9D55")
    ]
    with Image.open(path) as image:
        pixels = list(image.convert("RGB").get_flattened_data())
    for target in targets:
        matches = sum(
            1
            for pixel in pixels
            if max(abs(pixel[channel] - target[channel]) for channel in range(3)) <= 12
        )
        assert matches >= 3, f"expected rendered marker color {target} in {path}"


@pytest.mark.smoke
@pytest.mark.integration
def test_wse2_feedback_project_end_to_end(tmp_path):
    source_value = os.getenv("ORIGIN_FEEDBACK_PROJECT")
    if not source_value:
        pytest.skip("set ORIGIN_FEEDBACK_PROJECT to the WSe2 feedback OPJU")
    source = Path(source_value).expanduser().resolve()
    if not source.is_file():
        pytest.skip(f"feedback project does not exist: {source}")

    source_digest = _file_digest(source)
    before_pids = _origin_pids()
    if before_pids and os.getenv("ORIGIN_ALLOW_EXISTING") != "1":
        pytest.skip("an Origin process is already running; live regression will not risk attaching")

    controller = OriginController()
    try:
        started = controller.start(progid="Origin.Application", visible=False, attach=False)
        assert started.success, started.to_dict()
        assert started.data["owned"] is True
        assert started.data["activation_mode"] == "dispatch_ex_fresh_instance"
        assert started.data["observed_new_pid"] in started.data["new_pids"]
        assert started.data["pid_binding_confirmed"] is False

        opened = controller.open_project(
            source_path=str(source),
            working_copy_path=str(tmp_path / "feedback-working.opju"),
        )
        assert opened.success, opened.to_dict()

        audit = controller.list_objects()
        assert audit.success, audit.to_dict()
        assert [item["name"] for item in audit.data["workbooks"]] == ["WSe2Benchmark"]
        assert [item["name"] for item in audit.data["worksheets"]] == ["Data"]
        assert [item["name"] for item in audit.data["graphs"]] == ["Ion_vs_Lch"]
        assert (audit.data["worksheets"][0]["rows"], audit.data["worksheets"][0]["cols"]) == (
            26,
            13,
        )

        mixed = controller.read_worksheet(
            "[WSe2Benchmark]Data", r1=0, c1=0, r2=25, c2=12, data_format="auto"
        )
        assert mixed.success, mixed.to_dict()
        assert len(mixed.data["values"]) == 26
        assert all(len(row) == 13 for row in mixed.data["values"])
        assert mixed.data["values"][25][:3] == [80.0, 950.0, "this work"]

        categories = controller.read_worksheet(
            "[WSe2Benchmark]Data",
            r1=0,
            c1=8,
            r2=25,
            c2=8,
            data_format="categorical_label",
        )
        assert categories.success, categories.to_dict()
        assert Counter(row[0] for row in categories.data["values"]) == EXPECTED_CATEGORIES

        objects_before = _graph_object_snapshot(controller)
        configured_first = controller.configure_graph(
            graph_name="Ion_vs_Lch", options=_graph_options()
        )
        assert configured_first.success, configured_first.to_dict()
        objects_after_first = _graph_object_snapshot(controller)
        legend_first = _legend_text(controller)

        configured_second = controller.configure_graph(
            graph_name="Ion_vs_Lch", options=_graph_options()
        )
        assert configured_second.success, configured_second.to_dict()
        objects_after_second = _graph_object_snapshot(controller)
        legend_second = _legend_text(controller)
        assert objects_after_first["count"] >= objects_before["count"]
        assert objects_after_second["count"] == objects_after_first["count"]
        assert legend_second == legend_first

        styled_audit = controller.list_objects()
        _assert_project_structure(styled_audit)
        _assert_axis_state(controller)
        _assert_last_point_style(controller)

        strings = controller.execute_labtalk(
            script='codex_empty$="";codex_text$="this work";',
            result_string_variables=["codex_empty", "codex_text"],
        )
        assert strings.success, strings.to_dict()
        assert strings.data["string_output"] == {
            "codex_empty": "",
            "codex_text": "this work",
        }

        styled_png = tmp_path / "styled.png"
        exported = controller.export_graph(
            graph_name="Ion_vs_Lch",
            output_path=str(styled_png),
            export_format="png",
            overwrite="replace",
        )
        assert exported.success, exported.to_dict()
        styled_png = Path(exported.artifacts[0].path)
        _assert_marker_colors(styled_png)
        styled_pixels = _pixel_digest(styled_png)

        b_changed = controller.write_worksheet(
            "[WSe2Benchmark]Data", [[1900.0]], row=25, column=1
        )
        assert b_changed.success, b_changed.to_dict()
        b_changed_read = controller.read_worksheet(
            "[WSe2Benchmark]Data", r1=25, c1=1, r2=25, c2=2, data_format="auto"
        )
        assert b_changed_read.data["values"] == [[1900.0, "this work"]]

        b_edited_png = tmp_path / "b-edited.png"
        b_edited_export = controller.export_graph(
            graph_name="Ion_vs_Lch",
            output_path=str(b_edited_png),
            export_format="png",
            overwrite="replace",
        )
        assert b_edited_export.success, b_edited_export.to_dict()
        b_edited_png = Path(b_edited_export.artifacts[0].path)
        assert _pixel_digest(b_edited_png) != styled_pixels

        b_restored = controller.write_worksheet(
            "[WSe2Benchmark]Data", [[950.0]], row=25, column=1
        )
        assert b_restored.success, b_restored.to_dict()

        b_restored_png = tmp_path / "b-restored.png"
        b_restored_export = controller.export_graph(
            graph_name="Ion_vs_Lch",
            output_path=str(b_restored_png),
            export_format="png",
            overwrite="replace",
        )
        assert b_restored_export.success, b_restored_export.to_dict()
        b_restored_png = Path(b_restored_export.artifacts[0].path)
        assert _pixel_digest(b_restored_png) == styled_pixels

        c_changed = controller.write_worksheet(
            "[WSe2Benchmark]Data", [["EDIT-LINK-TEST"]], row=25, column=2
        )
        assert c_changed.success, c_changed.to_dict()
        c_changed_read = controller.read_worksheet(
            "[WSe2Benchmark]Data", r1=25, c1=1, r2=25, c2=2, data_format="auto"
        )
        assert c_changed_read.data["values"] == [[950.0, "EDIT-LINK-TEST"]]

        c_edited_png = tmp_path / "c-edited.png"
        c_edited_export = controller.export_graph(
            graph_name="Ion_vs_Lch",
            output_path=str(c_edited_png),
            export_format="png",
            overwrite="replace",
        )
        assert c_edited_export.success, c_edited_export.to_dict()
        c_edited_png = Path(c_edited_export.artifacts[0].path)
        assert _pixel_digest(c_edited_png) != styled_pixels

        c_restored = controller.write_worksheet(
            "[WSe2Benchmark]Data", [["this work"]], row=25, column=2
        )
        assert c_restored.success, c_restored.to_dict()
        restored_read = controller.read_worksheet(
            "[WSe2Benchmark]Data", r1=25, c1=0, r2=25, c2=2, data_format="auto"
        )
        assert restored_read.data["values"] == [[80.0, 950.0, "this work"]]

        c_restored_png = tmp_path / "c-restored.png"
        c_restored_export = controller.export_graph(
            graph_name="Ion_vs_Lch",
            output_path=str(c_restored_png),
            export_format="png",
            overwrite="replace",
        )
        assert c_restored_export.success, c_restored_export.to_dict()
        c_restored_png = Path(c_restored_export.artifacts[0].path)
        assert _pixel_digest(c_restored_png) == styled_pixels

        saved_path = tmp_path / "feedback-verified.opju"
        saved = controller.save_project_copy(target_path=str(saved_path))
        assert saved.success, saved.to_dict()

        reopened = controller.open_project(
            source_path=str(saved_path),
            working_copy_path=str(tmp_path / "feedback-reopened.opju"),
        )
        assert reopened.success, reopened.to_dict()
        reopened_audit = controller.list_objects()
        _assert_project_structure(reopened_audit)
        reopened_data = controller.read_worksheet(
            "[WSe2Benchmark]Data", r1=0, c1=0, r2=25, c2=12, data_format="auto"
        )
        assert reopened_data.success, reopened_data.to_dict()
        assert len(reopened_data.data["values"]) == 26
        assert all(len(row) == 13 for row in reopened_data.data["values"])
        assert reopened_data.data["values"][25][:3] == [80.0, 950.0, "this work"]

        reopened_categories = controller.read_worksheet(
            "[WSe2Benchmark]Data",
            r1=0,
            c1=8,
            r2=25,
            c2=8,
            data_format="categorical_label",
        )
        assert reopened_categories.success, reopened_categories.to_dict()
        assert Counter(row[0] for row in reopened_categories.data["values"]) == EXPECTED_CATEGORIES
        _assert_axis_state(controller)
        _assert_last_point_style(controller)
        assert _legend_text(controller) == legend_second

        reopened_png = tmp_path / "reopened.png"
        reopened_export = controller.export_graph(
            graph_name="Ion_vs_Lch",
            output_path=str(reopened_png),
            export_format="png",
            overwrite="replace",
        )
        assert reopened_export.success, reopened_export.to_dict()
        _assert_marker_colors(Path(reopened_export.artifacts[0].path))
    finally:
        stopped = controller.shutdown()
        assert stopped.success, stopped.to_dict()
        for _ in range(50):
            if not (_origin_pids() - before_pids):
                break
            time.sleep(0.2)
        assert not (_origin_pids() - before_pids)
        assert before_pids.issubset(_origin_pids())
        assert _file_digest(source) == source_digest
