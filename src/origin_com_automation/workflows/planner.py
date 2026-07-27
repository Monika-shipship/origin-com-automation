"""Offline compilation of immutable, intent-aware workflow plans."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..capabilities import capability_report
from ..data_inspection import DataInspectionError, inspect_data_source
from ..graphs.catalog import graph_catalog
from ..utils.hashing import sha256_file
from .spec import WorkflowSpec, workflow_spec_digest


@dataclass(frozen=True)
class PlannedStage:
    id: str
    mutation: bool
    target: str | None = None
    idempotency_key: str | None = None


@dataclass(frozen=True)
class WorkflowPlan:
    schema_version: int
    digest: str
    origin_version: str | None
    executor_executable: bool
    required_decisions: tuple[dict[str, Any], ...]
    blockers: tuple[dict[str, Any], ...]
    warnings: tuple[dict[str, Any], ...]
    safe_defaults: dict[str, Any]
    derived_values: dict[str, Any]
    source_previews: tuple[dict[str, Any], ...]
    expected_objects: tuple[dict[str, Any], ...]
    stages: tuple[PlannedStage, ...]
    capabilities: dict[str, Any]
    resolved_project_output: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["stages"] = [asdict(stage) for stage in self.stages]
        return payload


def _decision(
    field: str,
    message: str,
    *,
    choices: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "code": "SCIENTIFIC_DECISION_REQUIRED",
        "field": field,
        "message": message,
        "choices": list(choices or []),
    }


def _scientific_decisions(spec: WorkflowSpec) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    science = spec.scientific_contract
    if spec.intent in {"curve_analysis", "multi_device_compare", "fit_and_plot"}:
        if science.branch is None:
            decisions.append(
                _decision(
                    "scientific_contract.branch",
                    "Choose the exact scan branch or state that all rows are intended",
                    choices=["all", "forward", "reverse", "category", "explicit"],
                )
            )
    if spec.analyses or spec.plots:
        for role in ("x", "y"):
            if role not in science.input_units:
                decisions.append(
                    _decision(
                        f"scientific_contract.input_units.{role}",
                        f"Provide the physical unit for the {role.upper()} role",
                    )
                )
    for analysis in spec.analyses:
        method = analysis.method.strip().lower()
        prefix = "scientific_contract"
        if method == "derivative":
            if science.derivative_method is None:
                decisions.append(
                    _decision(
                        f"{prefix}.derivative_method",
                        "Choose the derivative algorithm and boundary convention",
                        choices=["dderivative", "differentiate", "forward", "backward", "central"],
                    )
                )
            if science.derivative_order is None:
                decisions.append(
                    _decision(
                        f"{prefix}.derivative_order",
                        "Provide the derivative order",
                    )
                )
        if method in {"linear_fit", "polynomial_fit", "nonlinear_fit"}:
            if science.fit_method is None:
                decisions.append(
                    _decision(
                        f"{prefix}.fit_method",
                        "Choose the fitting method and weighting convention",
                    )
                )
        if method == "nonlinear_fit" and science.model is None:
            decisions.append(
                _decision(f"{prefix}.model", "Provide the exact nonlinear fit model")
            )
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in decisions:
        if item["field"] not in seen:
            seen.add(item["field"])
            unique.append(item)
    return unique


def _idempotency_key(digest: str, stage_id: str, target: str | None) -> str:
    payload = json.dumps(
        {"digest": digest, "stage": stage_id, "target": target},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


_file_sha256 = sha256_file


def _stage(
    digest: str,
    stage_id: str,
    *,
    mutation: bool,
    target: str | None = None,
) -> PlannedStage:
    return PlannedStage(
        id=stage_id,
        mutation=mutation,
        target=target,
        idempotency_key=(
            _idempotency_key(digest, stage_id, target) if mutation else None
        ),
    )


def compile_workflow(
    spec: WorkflowSpec,
    *,
    origin_version: str | None,
    batch_item_count: int = 1,
) -> WorkflowPlan:
    """Inspect and compile a workflow without activating Origin or accepting a controller."""

    digest = workflow_spec_digest(spec)
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    previews: list[dict[str, Any]] = []
    expected_objects: list[dict[str, Any]] = []

    for source in spec.sources:
        source_path = Path(source.path).expanduser().resolve()
        if source.import_mode == "project":
            if not source_path.is_file():
                blockers.append(
                    {
                        "code": "PROJECT_INPUT_NOT_FOUND",
                        "source_id": source.id,
                        "path": str(source_path),
                    }
                )
                continue
            if source_path.suffix.lower() != ".opju":
                blockers.append(
                    {
                        "code": "PROJECT_INPUT_EXTENSION_INVALID",
                        "source_id": source.id,
                        "path": str(source_path),
                    }
                )
            previews.append(
                {
                    "source_id": source.id,
                    "source_sha256": _file_sha256(source_path),
                    "path": str(source_path),
                    "rows": None,
                    "columns": None,
                    "ambiguities": [],
                }
            )
            expected_objects.append(
                {
                    "logical_id": f"project:source:{source.id}",
                    "kind": "project",
                    "path": str(source_path),
                }
            )
            continue
        try:
            preview = inspect_data_source(
                source.path,
                sheet_name=source.sheet_name,
                has_header=source.has_header,
                header_row=source.header_row,
                encoding=source.encoding,
                delimiter=source.delimiter,
                decimal_convention=source.decimal_convention,
            )
        except DataInspectionError as exc:
            blockers.append(
                {
                    "code": "DATA_INSPECTION_FAILED",
                    "source_id": source.id,
                    "message": str(exc),
                }
            )
            continue
        preview = {"source_id": source.id, **preview}
        previews.append(preview)
        for ambiguity in preview["ambiguities"]:
            blockers.append({"source_id": source.id, **ambiguity})
        if source.expected_sha256 and (
            preview["source_sha256"].lower() != source.expected_sha256.lower()
        ):
            blockers.append(
                {
                    "code": "SOURCE_HASH_MISMATCH",
                    "source_id": source.id,
                    "expected": source.expected_sha256.lower(),
                    "actual": preview["source_sha256"].lower(),
                }
            )
        expected_objects.append(
            {
                "logical_id": f"worksheet:{source.id}",
                "kind": "worksheet",
                "requested_ref": source.worksheet_ref,
                "source_id": source.id,
            }
        )
        if source.import_mode == "normalized_linked":
            expected_objects.append(
                {
                    "logical_id": f"normalized_source:{source.id}",
                    "kind": "normalized_source",
                    "source_id": source.id,
                }
            )

    output = Path(spec.outputs.project_path).expanduser().resolve()
    if output.suffix.lower() != ".opju":
        blockers.append(
            {
                "code": "PROJECT_EXTENSION_INVALID",
                "message": "Project output must use the .opju extension",
            }
        )
    if output.exists() and spec.outputs.overwrite == "error":
        blockers.append(
            {"code": "OUTPUT_EXISTS", "path": str(output), "message": "Output exists"}
        )
    for source in spec.sources:
        if Path(source.path).expanduser().resolve() == output:
            blockers.append(
                {
                    "code": "SOURCE_OVERWRITE_FORBIDDEN",
                    "source_id": source.id,
                    "path": str(output),
                }
            )

    for formula in spec.formulas:
        expected_objects.append(
            {
                "logical_id": f"formula:{formula.id}",
                "kind": "column_formula",
                "worksheet_ref": formula.worksheet_ref,
                "column": formula.column,
            }
        )
    for analysis in spec.analyses:
        expected_objects.append(
            {
                "logical_id": f"analysis:{analysis.id}",
                "kind": "analysis_operation" if analysis.create_operation else "analysis_result",
                "worksheet_ref": analysis.worksheet_ref,
                "method": analysis.method,
            }
        )
    catalog = graph_catalog()
    for plot in spec.plots:
        capability = catalog.get(plot.graph_type)
        if capability is None:
            blockers.append(
                {
                    "code": "GRAPH_TYPE_UNKNOWN",
                    "plot_id": plot.id,
                    "graph_type": plot.graph_type,
                }
            )
        elif capability["status"] == "supported_unverified" and not plot.allow_unverified:
            blockers.append(
                {
                    "code": "GRAPH_ROUTE_UNVERIFIED",
                    "plot_id": plot.id,
                    "graph_type": plot.graph_type,
                }
            )
        expected_objects.append(
            {
                "logical_id": f"graph:{plot.id}",
                "kind": "graph",
                "requested_name": plot.graph_name,
                "graph_type": plot.graph_type,
            }
        )
    expected_objects.append(
        {"logical_id": "project:output", "kind": "project", "path": str(output)}
    )
    if spec.outputs.manifest_formats:
        expected_objects.append({"logical_id": "manifest:workflow", "kind": "manifest"})
    for export in spec.outputs.exports:
        expected_objects.append(
            {
                "logical_id": f"export:{export.graph_id}:{export.format}",
                "kind": "graph_export",
                "path": str(Path(export.path).expanduser().resolve()),
            }
        )

    stages: list[PlannedStage] = [
        _stage(digest, "preflight", mutation=False),
        _stage(digest, "start", mutation=True, target="session:owned"),
        _stage(digest, "prepare_copy", mutation=True, target="project:working"),
    ]
    stages.extend(
        _stage(
            digest,
            f"import:{source.id}",
            mutation=True,
            target=f"worksheet:{source.id}",
        )
        for source in spec.sources
    )
    stages.append(_stage(digest, "verify_data", mutation=False))
    stages.extend(
        _stage(
            digest,
            f"formula:{formula.id}",
            mutation=True,
            target=f"formula:{formula.id}",
        )
        for formula in spec.formulas
    )
    stages.extend(
        _stage(
            digest,
            f"analysis:{analysis.id}",
            mutation=True,
            target=f"analysis:{analysis.id}",
        )
        for analysis in spec.analyses
    )
    stages.extend(
        _stage(
            digest,
            f"plot:{plot.id}",
            mutation=True,
            target=f"graph:{plot.id}",
        )
        for plot in spec.plots
    )
    if spec.outputs.manifest_formats:
        stages.append(_stage(digest, "manifest", mutation=True, target="manifest:workflow"))
    stages.append(_stage(digest, "save", mutation=True, target="project:output"))
    stages.extend(
        _stage(
            digest,
            f"export:{export.graph_id}:{export.format}",
            mutation=True,
            target=f"export:{export.graph_id}:{export.format}",
        )
        for export in spec.outputs.exports
    )
    if spec.qa.reopen_project:
        stages.append(_stage(digest, "reopen_audit", mutation=False))
    stages.append(_stage(digest, "shutdown", mutation=True, target="session:owned"))

    source_total_bytes = sum(
        Path(source.path).expanduser().resolve().stat().st_size
        for source in spec.sources
        if Path(source.path).expanduser().resolve().is_file()
    )
    analysis_invocations = sum(len(item.y_columns) for item in spec.analyses)
    auto_milestone = (
        len(spec.sources) >= 2
        or analysis_invocations >= 3
        or (source_total_bytes >= 100 * 1024 * 1024 and bool(spec.analyses))
        or batch_item_count >= 3
    )
    requested_checkpoint_policy = spec.execution.checkpoint_policy
    resolved_checkpoint_policy = (
        "milestone"
        if requested_checkpoint_policy == "auto" and auto_milestone
        else "none"
        if requested_checkpoint_policy == "auto"
        else requested_checkpoint_policy
    )
    milestone_after = None
    if resolved_checkpoint_policy == "milestone":
        milestone_after = (
            "data"
            if len(spec.sources) >= 2 or source_total_bytes >= 100 * 1024 * 1024
            else "analysis"
            if spec.analyses
            else "data"
        )

    required = _scientific_decisions(spec)
    capabilities = capability_report(origin_version)
    return WorkflowPlan(
        schema_version=1,
        digest=digest,
        origin_version=origin_version,
        executor_executable=not blockers and not required,
        required_decisions=tuple(required),
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        safe_defaults={
            "fail_fast": spec.execution.fail_fast,
            "overwrite": spec.outputs.overwrite,
            "backend_policy": spec.execution.backend_policy,
            "checkpoint_policy": spec.execution.checkpoint_policy,
            "resolved_checkpoint_policy": resolved_checkpoint_policy,
            "milestone_after": milestone_after,
        },
        derived_values={
            "resolved_project_output": str(output),
            "source_total_bytes": source_total_bytes,
            "analysis_invocations": analysis_invocations,
            "batch_item_count": batch_item_count,
            "source_hashes": {
                item["source_id"]: item["source_sha256"] for item in previews
            },
        },
        source_previews=tuple(previews),
        expected_objects=tuple(expected_objects),
        stages=tuple(stages),
        capabilities=capabilities,
        resolved_project_output=str(output),
    )
