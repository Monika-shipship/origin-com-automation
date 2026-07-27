"""Strict declarative contracts for intent-aware Origin workflows."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from ..utils.hashing import canonical_digest
from .models import StrictModel


ColumnSelector = str | int


class SourceSpec(StrictModel):
    id: str
    path: str
    worksheet_ref: str | None = None
    sheet_name: str | None = None
    import_mode: Literal["linked", "snapshot", "normalized_linked", "project"] = "linked"
    has_header: bool | None = None
    header_row: int | None = Field(default=None, ge=0)
    encoding: str | None = None
    delimiter: str | None = None
    decimal_convention: Literal["dot", "comma"] | None = None
    expected_sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")
    template_policy: Literal["blank", "explicit", "reuse_existing"] = "blank"
    template_path: str | None = None
    template_sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")

    @model_validator(mode="after")
    def explicit_template_is_complete(self) -> "SourceSpec":
        if self.template_policy == "explicit" and not (
            self.template_path and self.template_sha256
        ):
            raise ValueError(
                "explicit template policy requires template_path and template_sha256"
            )
        return self


class RowRange(StrictModel):
    start: int = Field(ge=0)
    end: int = Field(ge=0)

    @model_validator(mode="after")
    def range_is_ordered(self) -> "RowRange":
        if self.end < self.start:
            raise ValueError("row range end must not precede start")
        return self


class RowSelection(StrictModel):
    ranges: list[RowRange] = Field(default_factory=list)
    order: Literal["input", "forward", "reverse"] = "input"
    branch: Literal["all", "forward", "reverse", "category", "explicit"] | None = None
    category_column: ColumnSelector | None = None
    category_values: list[str] = Field(default_factory=list)
    filters: list[str] = Field(default_factory=list)
    missing_rule: Literal["reject", "exclude", "preserve"] = "reject"


class ColumnRoles(StrictModel):
    x: ColumnSelector | None = None
    y: list[ColumnSelector] = Field(default_factory=list)
    label: ColumnSelector | None = None
    category: ColumnSelector | None = None
    group: ColumnSelector | None = None


class DataContract(StrictModel):
    roles: ColumnRoles = Field(default_factory=ColumnRoles)
    selection: RowSelection = Field(default_factory=RowSelection)
    duplicate_label_policy: Literal["reject", "qualify"] = "reject"
    column_types: dict[str, Literal["numeric", "text", "mixed", "categorical"]] = Field(
        default_factory=dict
    )


class ScientificContract(StrictModel):
    branch: Literal["all", "forward", "reverse", "category", "explicit"] | None = None
    scan_direction: Literal["increasing", "decreasing"] | None = None
    model: str | None = None
    fit_method: str | None = None
    derivative_method: str | None = None
    derivative_order: int | None = Field(default=None, ge=1)
    physical_definition: str | None = None
    normalization: str | None = None
    missing_value_rule: str | None = None
    outlier_rule: str | None = None
    device_dimensions: dict[str, float] = Field(default_factory=dict)
    material_parameters: dict[str, float] = Field(default_factory=dict)
    input_units: dict[str, str] = Field(default_factory=dict)
    output_units: dict[str, str] = Field(default_factory=dict)


class FormulaStep(StrictModel):
    id: str
    worksheet_ref: str
    column: ColumnSelector
    formula: str | None = None
    native_function: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    selection: RowSelection = Field(default_factory=RowSelection)
    recalculate_mode: Literal["none", "auto", "manual"] = "auto"

    @model_validator(mode="after")
    def one_expression_source(self) -> "FormulaStep":
        if bool(self.formula) == bool(self.native_function):
            raise ValueError("formula step requires exactly one of formula or native_function")
        return self


class AnalysisStep(StrictModel):
    id: str
    method: str
    worksheet_ref: str
    x_column: ColumnSelector
    y_columns: list[ColumnSelector] = Field(min_length=1)
    options: dict[str, Any] = Field(default_factory=dict)
    selection: RowSelection = Field(default_factory=RowSelection)
    backend_policy: Literal[
        "inherit", "origin_native_only", "origin_native_preferred", "external_explicit"
    ] = "inherit"
    create_operation: bool = True
    recalculate_mode: Literal["none", "auto", "manual"] = "auto"

    @model_validator(mode="after")
    def operation_modes_match(self) -> "AnalysisStep":
        if not self.create_operation and self.recalculate_mode != "none":
            raise ValueError(
                "recalculate_mode must be none when create_operation is false"
            )
        return self


class PlotStep(StrictModel):
    id: str
    graph_type: str
    roles: dict[str, ColumnSelector | list[ColumnSelector]]
    graph_name: str | None = None
    layout_policy: Literal["auto", "explicit"] = "auto"
    options: dict[str, Any] = Field(default_factory=dict)
    allow_unverified: bool = False


class ExportSpec(StrictModel):
    graph_id: str
    path: str
    format: Literal["png", "tiff", "pdf", "svg"]


class WorkflowOutputs(StrictModel):
    project_path: str
    overwrite: Literal["error", "replace"] = "error"
    exports: list[ExportSpec] = Field(default_factory=list)
    manifest_formats: list[Literal["notes", "json", "text"]] = Field(default_factory=list)


class ExecutionPolicy(StrictModel):
    backend_policy: Literal[
        "origin_native_only", "origin_native_preferred", "external_explicit"
    ] = "origin_native_preferred"
    fail_fast: bool = True
    checkpoint_policy: Literal["auto", "none", "milestone", "phase", "mutation"] = "auto"
    idempotency_key: str | None = None


class WorkflowQA(StrictModel):
    critical_columns: list[str] = Field(default_factory=list)
    representative_rows: list[int] = Field(default_factory=list)
    minimum_rows: int = Field(default=1, ge=1)
    expected_colors: list[str] = Field(default_factory=list)
    require_connector: bool = True
    require_native_operations: bool = True
    reopen_project: bool = False


class WorkflowSpec(StrictModel):
    schema_version: Literal[1] = 1
    intent: Literal[
        "import_and_plot",
        "curve_analysis",
        "multi_device_compare",
        "fit_and_plot",
        "statistical_summary",
        "engineering_figure",
        "custom",
    ]
    description: str | None = None
    sources: list[SourceSpec] = Field(min_length=1)
    data_contract: DataContract = Field(default_factory=DataContract)
    scientific_contract: ScientificContract = Field(default_factory=ScientificContract)
    formulas: list[FormulaStep] = Field(default_factory=list)
    analyses: list[AnalysisStep] = Field(default_factory=list)
    plots: list[PlotStep] = Field(default_factory=list)
    outputs: WorkflowOutputs
    execution: ExecutionPolicy = Field(default_factory=ExecutionPolicy)
    qa: WorkflowQA = Field(default_factory=WorkflowQA)
    visible: bool = False

    @model_validator(mode="after")
    def step_ids_are_unique(self) -> "WorkflowSpec":
        for label, values in (
            ("source", [item.id for item in self.sources]),
            ("formula", [item.id for item in self.formulas]),
            ("analysis", [item.id for item in self.analyses]),
            ("plot", [item.id for item in self.plots]),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{label} ids must be unique")
        return self


def workflow_spec_digest(spec: WorkflowSpec) -> str:
    return canonical_digest(spec)
