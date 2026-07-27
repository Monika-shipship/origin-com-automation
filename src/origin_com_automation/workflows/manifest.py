"""Canonical, redacted reproducibility manifests for workflow delivery."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from ..contracts import Artifact
from .planner import WorkflowPlan
from .spec import WorkflowSpec


def _display_path(value: str, *, redact: bool) -> str:
    path = Path(value).expanduser().resolve()
    return f"<source>/{path.name}" if redact else str(path)


def build_workflow_manifest(
    spec: WorkflowSpec,
    plan: WorkflowPlan,
    ledger: dict[str, Any],
    *,
    plugin_version: str,
    origin_version: str | None,
    redact_paths: bool = True,
) -> dict[str, Any]:
    hashes = plan.derived_values.get("source_hashes", {})
    return {
        "schema_version": 1,
        "workflow_digest": plan.digest,
        "intent": spec.intent,
        "description": spec.description,
        "plugin_version": plugin_version,
        "origin_version": origin_version,
        "sources": [
            {
                "id": source.id,
                "path": _display_path(source.path, redact=redact_paths),
                "sha256": hashes.get(source.id),
                "import_mode": source.import_mode,
                "worksheet_ref": source.worksheet_ref,
                "sheet_name": source.sheet_name,
                "template_policy": source.template_policy,
            }
            for source in spec.sources
        ],
        "scientific_contract": spec.scientific_contract.model_dump(mode="json", exclude_none=True),
        "data_contract": spec.data_contract.model_dump(mode="json", exclude_none=True),
        "formulas": [item.model_dump(mode="json", exclude_none=True) for item in spec.formulas],
        "analyses": [item.model_dump(mode="json", exclude_none=True) for item in spec.analyses],
        "plots": [item.model_dump(mode="json", exclude_none=True) for item in spec.plots],
        "execution_policy": spec.execution.model_dump(mode="json", exclude_none=True),
        "qa_contract": spec.qa.model_dump(mode="json", exclude_none=True),
        "completed_stages": list(ledger.get("completed_stage_ids", [])),
        "object_refs": dict(ledger.get("objects", {})),
        "warnings": list(ledger.get("warnings", [])),
        "unverified": [
            item for item in ledger.get("audit_checks", []) if item.get("status") == "unverified"
        ],
        "outputs": {
            "project": _display_path(spec.outputs.project_path, redact=redact_paths),
            "exports": [
                {**item.model_dump(mode="json"), "path": _display_path(item.path, redact=redact_paths)}
                for item in spec.outputs.exports
            ],
        },
    }


def write_manifest_artifacts(
    manifest: dict[str, Any],
    base_path: str | Path,
    *,
    formats: Iterable[str],
) -> list[Artifact]:
    base = Path(base_path).expanduser().resolve()
    base.parent.mkdir(parents=True, exist_ok=True)
    artifacts: list[Artifact] = []
    for format_name in formats:
        if format_name == "json":
            path = base.with_suffix(".json")
            content = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        elif format_name == "text":
            path = base.with_suffix(".txt")
            content = "Origin COM Automation Workflow Manifest\n\n" + json.dumps(
                manifest, ensure_ascii=False, indent=2, sort_keys=True
            ) + "\n"
        else:
            continue
        path.write_text(content, encoding="utf-8")
        artifacts.append(Artifact(str(path), f"workflow_manifest_{format_name}"))
    return artifacts

