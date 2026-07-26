import os
import time

import psutil
import pytest

from origin_com_automation.com.discovery import discover_registrations
from origin_com_automation.com.origin_api import OriginController, is_origin_process_name
from origin_com_automation.graphs.preview import inspect_png
from origin_com_automation.workflows.executor import execute_figure
from origin_com_automation.workflows.figurespec import FigureSpec, figure_spec_digest


def origin_pids() -> set[int]:
    return {
        int(process.info["pid"])
        for process in psutil.process_iter(["pid", "name"])
        if is_origin_process_name(str(process.info.get("name", "")))
    }


class Context:
    def __init__(self):
        self.stages = []

    def stage(self, value, *, mutation=False):
        self.stages.append((value, mutation))


@pytest.mark.smoke
@pytest.mark.integration
def test_live_two_item_figurespec_batch(tmp_path):
    if os.getenv("ORIGIN_LIVE_SMOKE") != "1":
        pytest.skip("set ORIGIN_LIVE_SMOKE=1 to activate Origin COM")
    if not any(item.available for item in discover_registrations()):
        pytest.skip("no registered Origin COM server was detected")
    before = origin_pids()
    if before and os.getenv("ORIGIN_ALLOW_EXISTING") != "1":
        pytest.skip("an Origin process is already running; live smoke will not risk attaching")

    results = []
    for index in range(2):
        source = tmp_path / f"batch-{index}.csv"
        source.write_text("x,y\n0,1\n1,3\n2,5\n", encoding="ascii")
        project = tmp_path / f"batch-{index}.opju"
        image = tmp_path / f"batch-{index}.png"
        spec = FigureSpec.model_validate(
            {
                "route": "data_to_project",
                "input": {
                    "path": str(source),
                    "worksheet_ref": f"BatchData{index}",
                    "has_header": True,
                },
                "plots": [
                    {
                        "id": "main",
                        "graph_type": "scatter",
                        "roles": {
                            "worksheet": f"BatchData{index}",
                            "x": "A",
                            "y": "B",
                        },
                        "graph_name": f"BatchGraph{index}",
                    }
                ],
                "outputs": {
                    "project_path": str(project),
                    "exports": [
                        {"graph_id": "main", "path": str(image), "format": "png"}
                    ],
                },
                "qa": {"critical_columns": ["A", "B"], "minimum_rows": 3},
            }
        )
        context = Context()
        result = execute_figure(
            OriginController(),
            spec,
            expected_digest=figure_spec_digest(spec),
            context=context,
        )
        assert result["success"] is True, result
        assert result["completed_stages"][-1] == "shutdown"
        assert project.stat().st_size > 0
        metrics = inspect_png(image)
        assert metrics["nonblank_ratio"] > 0
        results.append(result)

    assert len(results) == 2
    assert results[0]["digest"] != results[1]["digest"]
    for _ in range(100):
        if not (origin_pids() - before):
            break
        time.sleep(0.2)
    assert not (origin_pids() - before)
    assert before.issubset(origin_pids())
