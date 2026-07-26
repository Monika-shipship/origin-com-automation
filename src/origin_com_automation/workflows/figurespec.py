"""Strict declarative figure specifications and preflight compilation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..graphs.catalog import graph_catalog


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FigureInput(StrictModel):
    path: str
    worksheet_ref: str | None = None
    sheet_name: str | None = None
    has_header: bool | None = None
    source_mode: Literal["linked", "snapshot"] = "linked"


class FigureAnalysis(StrictModel):
    id: str
    method: str
    worksheet_ref: str
    x_column: str | int
    y_column: str | int
    options: dict[str, Any] = Field(default_factory=dict)
    backend: Literal["origin_native", "python"] = "origin_native"
    create_operation: bool = True
    recalculate_mode: Literal["none", "auto", "manual"] = "auto"
    row_start: int = 0
    row_end: int = -1

    @model_validator(mode="after")
    def execution_modes_are_explicit(self) -> "FigureAnalysis":
        reserved = sorted(
            set(self.options) & {"backend", "create_operation", "recalculate_mode"}
        )
        if reserved:
            raise ValueError(
                "analysis options contain reserved execution fields: "
                + ", ".join(reserved)
            )
        if not self.create_operation and self.recalculate_mode != "none":
            raise ValueError(
                "recalculate_mode must be none when create_operation is false"
            )
        return self


class FigurePlot(StrictModel):
    id: str
    graph_type: str
    roles: dict[str, str | int | list[str | int]]
    graph_name: str | None = None
    allow_unverified: bool = False


class FigureExport(StrictModel):
    graph_id: str
    path: str
    format: Literal["png", "tiff", "pdf", "svg"]


class FigureOutputs(StrictModel):
    project_path: str
    overwrite: Literal["error", "replace"] = "error"
    exports: list[FigureExport] = Field(default_factory=list)


class FigureQA(StrictModel):
    critical_columns: list[str] = Field(default_factory=list)
    minimum_rows: int = Field(default=1, ge=1)
    expected_colors: list[str] = Field(default_factory=list)
    reopen_project: bool = False


class FigureSpec(StrictModel):
    schema_version: Literal[1] = 1
    route: Literal["data_to_project", "restyle_project"]
    input: FigureInput
    analyses: list[FigureAnalysis] = Field(default_factory=list)
    plots: list[FigurePlot] = Field(default_factory=list)
    outputs: FigureOutputs
    qa: FigureQA = Field(default_factory=FigureQA)
    visible: bool = False

    @model_validator(mode="after")
    def unique_ids(self) -> "FigureSpec":
        analysis_ids = [item.id for item in self.analyses]
        plot_ids = [item.id for item in self.plots]
        if len(analysis_ids) != len(set(analysis_ids)):
            raise ValueError("analysis ids must be unique")
        if len(plot_ids) != len(set(plot_ids)):
            raise ValueError("plot ids must be unique")
        return self


def figure_spec_digest(spec: FigureSpec) -> str:
    payload = spec.model_dump(mode="json", exclude_none=True)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compile_figure_spec(
    spec: FigureSpec,
    *,
    origin_version: str | None,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    source = Path(spec.input.path).expanduser().resolve()
    if not source.is_file():
        blockers.append(f"input does not exist: {source}")
    if spec.route == "data_to_project" and source.suffix.lower() not in {
        ".csv", ".tsv", ".xls", ".xlsx", ".xlsm"
    }:
        blockers.append("data_to_project requires CSV, TSV, or Excel input")
    if spec.route == "restyle_project" and source.suffix.lower() != ".opju":
        blockers.append("restyle_project requires an OPJU input")
    output = Path(spec.outputs.project_path).expanduser().resolve()
    if output.suffix.lower() != ".opju":
        blockers.append("project output must use .opju")
    if output.exists() and spec.outputs.overwrite == "error":
        blockers.append(f"project output already exists: {output}")
    if source == output:
        blockers.append("project output must not overwrite the input")
    catalog = graph_catalog()
    plot_capabilities: dict[str, str] = {}
    for plot in spec.plots:
        entry = catalog.get(plot.graph_type)
        if entry is None:
            blockers.append(f"unknown graph type for {plot.id}: {plot.graph_type}")
            continue
        plot_capabilities[plot.id] = entry["status"]
        if entry["status"] == "supported_unverified" and not plot.allow_unverified:
            blockers.append(
                f"plot {plot.id} is supported-unverified and requires explicit allow_unverified"
            )
        elif entry["status"] == "supported_unverified":
            warnings.append(f"plot {plot.id} uses a supported-unverified graph route")
    input_stage = (
        "connector"
        if spec.route == "data_to_project" and spec.input.source_mode == "linked"
        else "input"
    )
    stages = [
        {"id": "preflight", "mutation": False},
        {"id": "start", "mutation": True},
        {"id": input_stage, "mutation": True},
    ]
    if any(item.backend == "origin_native" and item.create_operation for item in spec.analyses):
        stages.append({"id": "native_operation", "mutation": True})
    if any(item.backend == "origin_native" and not item.create_operation for item in spec.analyses):
        stages.append({"id": "native_analysis", "mutation": True})
    if any(item.backend == "python" for item in spec.analyses):
        stages.append({"id": "analysis", "mutation": True})
    if spec.plots:
        stages.append({"id": "plot", "mutation": True})
    stages.extend(
        [
            {"id": "save", "mutation": True},
            *([{"id": "export", "mutation": True}] if spec.outputs.exports else []),
            {"id": "qa", "mutation": False},
            {"id": "shutdown", "mutation": True},
        ]
    )
    return {
        "schema_version": 1,
        "digest": figure_spec_digest(spec),
        "route": spec.route,
        "origin_version": origin_version,
        "executor_executable": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "stages": stages,
        "plot_capabilities": plot_capabilities,
        "execution_modes": {
            "source_mode": spec.input.source_mode,
            "analysis_backends": sorted({item.backend for item in spec.analyses}),
            "native_operation_count": sum(
                item.backend == "origin_native" and item.create_operation
                for item in spec.analyses
            ),
        },
        "resolved_input": str(source),
        "resolved_project_output": str(output),
    }
