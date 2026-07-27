from __future__ import annotations

import json
import os
import time
from pathlib import Path

import psutil
import pytest

from origin_com_automation.com.origin_api import OriginController, is_origin_process_name
from origin_com_automation.graphs.preview import inspect_png
from origin_com_automation.native.operations import build_get_operation_command
from origin_com_automation.workflows.engine import WorkflowEngine
from origin_com_automation.workflows.spec import WorkflowSpec, workflow_spec_digest


def _origin_pids() -> set[int]:
    return {
        int(process.info["pid"])
        for process in psutil.process_iter(["pid", "name"])
        if is_origin_process_name(str(process.info.get("name", "")))
    }


def _require_live_origin() -> set[int]:
    if os.getenv("ORIGIN_LIVE_SMOKE") != "1":
        pytest.skip("set ORIGIN_LIVE_SMOKE=1 to activate Origin COM")
    from origin_com_automation.com.discovery import discover_registrations

    if not any(item.available for item in discover_registrations()):
        pytest.skip("no registered Origin COM server was detected")
    before = _origin_pids()
    if before and os.getenv("ORIGIN_ALLOW_EXISTING") != "1":
        pytest.skip("an Origin process is already running; live smoke will not risk attaching")
    return before


def _assert_owned_exit(before: set[int]) -> None:
    for _ in range(100):
        if not (_origin_pids() - before):
            break
        time.sleep(0.2)
    assert not (_origin_pids() - before)
    assert before.issubset(_origin_pids())


@pytest.mark.smoke
@pytest.mark.integration
def test_live_intent_workflow_native_derivative_manifest_and_reopen(tmp_path):
    before = _require_live_origin()
    source = tmp_path / "workflow-source.csv"
    source.write_text("x,y\n0,0\n1,1\n2,4\n3,9\n4,16\n", encoding="ascii")
    project = tmp_path / "workflow-result.opju"
    image = tmp_path / "workflow-result.png"
    reopened_copy = tmp_path / "workflow-reopened.opju"
    spec = WorkflowSpec.model_validate(
        {
            "intent": "curve_analysis",
            "description": "Origin-native derivative workflow smoke",
            "sources": [
                {
                    "id": "data",
                    "path": str(source),
                    "worksheet_ref": "[WorkflowData]Sheet1",
                    "import_mode": "linked",
                    "has_header": True,
                }
            ],
            "scientific_contract": {
                "branch": "all",
                "derivative_method": "differentiate",
                "derivative_order": 1,
                "input_units": {"x": "s", "y": "V"},
                "output_units": {"derivative": "V/s"},
            },
            "analyses": [
                {
                    "id": "derivative",
                    "method": "derivative",
                    "worksheet_ref": "[WorkflowData]Sheet1",
                    "x_column": "A",
                    "y_columns": ["B"],
                    "backend_policy": "origin_native_only",
                    "create_operation": True,
                    "recalculate_mode": "auto",
                }
            ],
            "plots": [
                {
                    "id": "main",
                    "graph_type": "scatter",
                    "roles": {
                        "worksheet": "[WorkflowData]Sheet1",
                        "x": "A",
                        "y": ["B"],
                    },
                    "graph_name": "WorkflowGraph",
                }
            ],
            "outputs": {
                "project_path": str(project),
                "exports": [{"graph_id": "main", "path": str(image), "format": "png"}],
                "manifest_formats": ["notes", "json", "text"],
            },
            "execution": {
                "backend_policy": "origin_native_only",
                "fail_fast": True,
                "checkpoint_policy": "phase",
            },
            "qa": {
                "critical_columns": ["A", "B"],
                "representative_rows": [0, 4],
                "minimum_rows": 5,
                "require_connector": True,
                "require_native_operations": True,
                "reopen_project": True,
            },
        }
    )

    controllers: list[OriginController] = []

    def factory() -> OriginController:
        controller = OriginController()
        controllers.append(controller)
        return controller

    engine = WorkflowEngine(factory)
    try:
        plan = engine.plan(spec, origin_version="10.1.0.178")
        assert plan.executor_executable, plan.to_dict()
        result = engine.execute(
            spec,
            expected_digest=workflow_spec_digest(spec),
            idempotency_key="live-workflow-030",
        )
        assert result["success"], result
    finally:
        engine.close()

    assert project.is_file() and project.stat().st_size > 100
    assert image.is_file() and image.stat().st_size > 100
    metrics = inspect_png(image)
    assert metrics["nonblank_ratio"] > 0
    assert metrics["qa_passed"] is True
    ledger = json.loads(Path(result["ledger_path"]).read_text(encoding="utf-8"))
    assert ledger["state"] == "succeeded"
    assert ledger["checkpoints"]
    assert ledger["objects"]["analysis:derivative"]["xfunction"] == "differentiate"
    operation_range = next(
        iter(ledger["objects"]["analysis:derivative"]["outputs"].values())
    )
    worksheet_ref = ledger["objects"]["worksheet:data"]["worksheet_ref"]
    manifest_files = [
        Path(item["path"])
        for item in result["artifacts"]
        if item["kind"].startswith("workflow_manifest")
    ]
    assert manifest_files and all(path.is_file() and path.stat().st_size > 0 for path in manifest_files)
    _assert_owned_exit(before)

    reopened = OriginController()
    try:
        started = reopened.start(progid="Origin.Application", visible=False, attach=False)
        assert started.success, started.to_dict()
        opened = reopened.open_project(
            source_path=str(project), working_copy_path=str(reopened_copy)
        )
        assert opened.success, opened.to_dict()
        objects = reopened.list_objects()
        assert objects.success, objects.to_dict()
        assert any(item["name"] == "WorkflowGraph" for item in objects.data["graphs"])
        connector = reopened.manage_connector(action="info", worksheet_ref=worksheet_ref)
        assert connector.success and connector.data["connected"] is True, connector.to_dict()
        operation = reopened.execute_labtalk(script=build_get_operation_command(operation_range))
        assert operation.success, operation.to_dict()
        note = reopened.manage_note(action="info", note_ref="Codex Workflow Manifest")
        assert note.success and workflow_spec_digest(spec) in note.data["text"], note.to_dict()
    finally:
        stopped = reopened.shutdown()
        if not stopped.success:
            assert stopped.error_code == "SHUTDOWN_UNCONFIRMED", stopped.to_dict()
    _assert_owned_exit(before)
