from pathlib import Path

import pytest

from origin_com_automation.contracts import ResultEnvelope
from origin_com_automation.workflows.audit import AuditTarget, run_targeted_audit
from origin_com_automation.workflows.manifest import build_workflow_manifest, write_manifest_artifacts
from origin_com_automation.workflows.planner import compile_workflow
from origin_com_automation.workflows.spec import WorkflowSpec


class AuditController:
    def read_worksheet(self, name, **kwargs):
        return ResultEnvelope.ok({"worksheet_ref": name, "values": [[1, 2], [3, 4]], "rows": 2})

    def manage_connector(self, **kwargs):
        return ResultEnvelope.ok({"worksheet_ref": kwargs["worksheet_name"], "connected": True, "source_exists": True})

    def get_analysis_operation(self, **kwargs):
        return ResultEnvelope.ok({"operation_ref": kwargs["operation_ref"], "recalculate_mode": "auto", "exists": True})

    def list_objects(self):
        return ResultEnvelope.ok({"graphs": [{"name": "Graph1", "bindings": {"x": "A", "y": ["B"]}, "axes": {"x": "linear", "y": "log10"}}]})


def test_targeted_audit_rejects_unbounded_project_requests():
    with pytest.raises(ValueError, match="bounded"):
        run_targeted_audit(AuditController(), [AuditTarget(kind="graph", ref="*")])


def test_targeted_audit_checks_data_connector_operation_graph_and_file(tmp_path):
    artifact = tmp_path / "result.opju"
    artifact.write_bytes(b"verified project")
    targets = [
        AuditTarget(kind="worksheet", ref="[Data]Sheet1", expected={"minimum_rows": 2, "representative_values": {"0,1": 2}}),
        AuditTarget(kind="connector", ref="[Data]Sheet1", expected={"connected": True}),
        AuditTarget(kind="operation", ref="operation:fit", expected={"recalculate_mode": "auto"}),
        AuditTarget(kind="graph", ref="Graph1", expected={"bindings": {"x": "A", "y": ["B"]}, "axes": {"y": "log10"}}),
        AuditTarget(kind="file", ref=str(artifact), expected={"minimum_size": 8}),
        AuditTarget(kind="formula", ref="[Data]Sheet1!C", expected={"formula": "col(B)*2"}),
    ]
    report = run_targeted_audit(AuditController(), targets)
    statuses = {item["target"]["kind"]: item["status"] for item in report["checks"]}
    assert statuses == {
        "worksheet": "verified",
        "connector": "verified",
        "operation": "verified",
        "graph": "verified",
        "file": "verified",
        "formula": "unverified",
    }
    assert report["summary"] == {"verified": 5, "warning": 0, "unverified": 1, "failed": 0}


def test_manifest_is_canonical_redacted_and_written_as_json_and_text(tmp_path):
    source = tmp_path / "input.csv"
    source.write_text("x,y\n1,2\n", encoding="utf-8")
    spec = WorkflowSpec.model_validate({
        "intent": "import_and_plot",
        "sources": [{"id": "data", "path": str(source)}],
        "scientific_contract": {"input_units": {"x": "V", "y": "A"}},
        "outputs": {"project_path": str(tmp_path / "result.opju"), "manifest_formats": ["json", "text"]},
    })
    plan = compile_workflow(spec, origin_version="10.1.0.178")
    manifest = build_workflow_manifest(
        spec,
        plan,
        {"warnings": [], "objects": {"worksheet:data": {"rows": 1}}, "completed_stage_ids": ["import:data"]},
        plugin_version="0.3.0",
        origin_version="10.1.0.178",
    )
    assert manifest["workflow_digest"] == plan.digest
    assert manifest["plugin_version"] == "0.3.0"
    assert manifest["sources"][0]["sha256"]
    assert str(tmp_path) not in manifest["sources"][0]["path"]
    artifacts = write_manifest_artifacts(manifest, tmp_path / "manifest", formats=["json", "text"])
    assert {Path(item.path).suffix for item in artifacts} == {".json", ".txt"}

