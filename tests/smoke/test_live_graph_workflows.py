import os
import time
from pathlib import Path

import psutil
import pytest

from origin_com_automation.com.discovery import discover_registrations
from origin_com_automation.com.origin_api import OriginController, is_origin_process_name
from origin_com_automation.graphs.templates import discover_templates


def origin_pids() -> set[int]:
    return {
        int(process.info["pid"])
        for process in psutil.process_iter(["pid", "name"])
        if is_origin_process_name(str(process.info.get("name", "")))
    }


@pytest.mark.smoke
@pytest.mark.integration
def test_live_graph_preview_pixels_layout_and_template_discovery(tmp_path):
    if os.getenv("ORIGIN_LIVE_SMOKE") != "1":
        pytest.skip("set ORIGIN_LIVE_SMOKE=1 to activate Origin COM")
    registrations = [item for item in discover_registrations() if item.available]
    if not registrations:
        pytest.skip("no registered Origin COM server was detected")
    before = origin_pids()
    if before and os.getenv("ORIGIN_ALLOW_EXISTING") != "1":
        pytest.skip("an Origin process is already running; live smoke will not risk attaching")

    install_root = Path(registrations[0].server_path).resolve().parent
    templates = discover_templates([str(install_root)])
    assert all(item["sha256"] and item["size"] for item in templates)

    controller = OriginController()
    try:
        started = controller.start(progid="Origin.Application", visible=False, attach=False)
        assert started.success, started.to_dict()
        source = tmp_path / "graph.csv"
        source.write_text("x,y,y2\n0,0,0\n1,1,2\n2,4,3\n3,9,5\n", encoding="ascii")
        imported = controller.import_data(
            file_path=str(source), worksheet_name="GraphData", has_header=True
        )
        assert imported.success, imported.to_dict()
        graph = controller.create_plot(
            worksheet_name=imported.data["worksheet_ref"],
            graph_type="scatter",
            x_column="A",
            y_columns=["B"],
            graph_name="LiveGraph",
        )
        assert graph.success, graph.to_dict()
        layout = controller.manage_graph_layout(
            action="dual_y", graph_ref=graph.data["graph_id"]
        )
        assert layout.success, layout.to_dict()
        assert layout.data["status"] == "supported_unverified"

        preview_path = tmp_path / "preview.png"
        preview = controller.view_graph(
            graph_name=graph.data["graph_id"], output_path=str(preview_path)
        )
        assert preview.success, preview.to_dict()
        metrics = preview.data["pixel_metrics"]
        assert metrics["dimensions"][0] > 100
        assert metrics["dimensions"][1] > 100
        assert metrics["nonblank_ratio"] > 0
        assert metrics["unique_color_count"] > 2
        assert preview_path.stat().st_size > 0
    finally:
        stopped = controller.shutdown()
        assert stopped.success, stopped.to_dict()
    for _ in range(100):
        if not (origin_pids() - before):
            break
        time.sleep(0.2)
    assert not (origin_pids() - before)
    assert before.issubset(origin_pids())
