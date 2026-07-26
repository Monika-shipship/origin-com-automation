"""FastMCP stdio server for safe Origin automation."""

from __future__ import annotations

import logging
import sys
import base64
import json
from copy import deepcopy
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.tools import Tool
from mcp.types import ImageContent, TextContent
from pydantic import BaseModel, ConfigDict, Field

from .capabilities import capability_report
from .com.origin_api import OriginController
from .contracts import ResultEnvelope
from .data_inspection import DataInspectionError, inspect_data_source
from .graphs.catalog import graph_catalog
from .graphs.palettes import palette_catalog
from .graphs.preview import inspect_png
from .graphs.templates import discover_templates
from .native.common import FileRef, OutputRef, RangeRef
from .knowledge import query_knowledge
from .tools.health import health_check
from .workflows.executor import execute_figure
from .workflows.figurespec import FigureSpec, compile_figure_spec, figure_spec_digest
from .workflows.tasks import TaskManager

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


class StrictOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NativeRangeInput(StrictOptions):
    type: Literal["range"]
    value: str


class NativeFileInput(StrictOptions):
    type: Literal["file"]
    value: str


class NativeStringInput(StrictOptions):
    type: Literal["string"]
    value: str


class NativeNumberInput(StrictOptions):
    type: Literal["number"]
    value: float


class NativeIntegerInput(StrictOptions):
    type: Literal["integer"]
    value: int


class NativeBooleanInput(StrictOptions):
    type: Literal["boolean"]
    value: bool


class NativeOutputInput(StrictOptions):
    type: Literal["output"] = "output"
    value: str


NativeParameterInput = Annotated[
    NativeRangeInput
    | NativeFileInput
    | NativeStringInput
    | NativeNumberInput
    | NativeIntegerInput
    | NativeBooleanInput,
    Field(discriminator="type"),
]


def _decode_native_parameter(value: NativeParameterInput) -> Any:
    if isinstance(value, NativeRangeInput):
        return RangeRef(value.value)
    if isinstance(value, NativeFileInput):
        return FileRef(value.value)
    return value.value


class AnalysisOptions(StrictOptions):
    backend: Literal["python", "origin_native"] = "origin_native"
    degree: int | None = None
    polyorder: int | None = None
    window: int | None = None
    order: int | None = None
    derivative_method: Literal["gradient", "forward", "backward", "central"] | None = None
    edge_order: Literal[1, 2] | None = None
    prominence: float | None = None
    distance: float | None = None
    height: float | None = None
    model: Literal["exponential", "gaussian"] | None = None
    initial_guess: list[float] | None = None
    maxfev: int | None = None
    bounds: list[list[float]] | None = None
    parameter_names: list[str] | None = None
    interpolation_kind: Literal["linear", "nearest", "cubic"] | None = None
    interpolation_points: list[float] | None = None
    normalization_method: Literal["min_max", "z_score", "area"] | None = None
    sample_spacing: Annotated[float, Field(gt=0)] | None = None
    correlation_method: Literal["pearson", "spearman"] | None = None
    alternative: Literal["two-sided", "less", "greater"] | None = None
    population_mean: float | None = None
    equal_variance: bool | None = None
    groups: list[list[float]] | None = None
    components: Annotated[int, Field(ge=1, le=2)] | None = None
    standardize: bool | None = None
    create_operation: bool = True
    recalculate_mode: Literal["none", "auto", "manual"] = "auto"


class AnalysisFilter(StrictOptions):
    column: Literal["x", "y"]
    operator: Literal["gt", "ge", "lt", "le", "eq", "ne"]
    value: float


class CreatePlotOptions(StrictOptions):
    template: str | None = None


class PlotStyleOptions(StrictOptions):
    plot_index: Annotated[int, Field(ge=1)] = 1
    color_index: int | None = None
    line_connection: str | int | None = None


class GraphDataBinding(StrictOptions):
    worksheet_name: str
    x_column: str | int
    y_columns: list[str | int]
    label_column: str | int | None = None
    plot_type: Literal["line", "scatter", "line_symbol", "bar"] = "line"


HexColor = Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]
PositiveFloat = Annotated[float, Field(gt=0)]


class CategoryMarkerOptions(StrictOptions):
    color: HexColor | None = None
    shape: Literal[
        "circle",
        "square",
        "triangle_up",
        "triangle_down",
        "diamond",
        "hexagon",
        "star",
        "cross",
        "x",
    ] | None = None
    fill: Literal["solid", "open", "hollow"] | None = None
    size: PositiveFloat | None = None


class CategoricalStyleOptions(StrictOptions):
    plot_index: Annotated[int, Field(ge=1)] = 1
    worksheet_name: str | None = None
    category_column: str | int
    categories: Annotated[dict[str, CategoryMarkerOptions], Field(min_length=1)]


class CategoricalLegendOptions(StrictOptions):
    mode: Literal["categorical"] = "categorical"
    source: Literal["plot_style_mapping"] = "plot_style_mapping"
    plot_index: Annotated[int, Field(ge=1)] = 1
    position: Literal["top_right"] = "top_right"
    font_size: PositiveFloat | None = None
    line_spacing: PositiveFloat | None = None
    border: bool = False
    background: Literal["transparent"] = "transparent"
    replace_existing: bool = True
    show_all_categories: bool | None = None


class GraphConfigurationOptions(StrictOptions):
    x_min: float | None = None
    x_max: float | None = None
    y_min: float | None = None
    y_max: float | None = None
    x_tick_step: float | None = None
    y_tick_step: float | None = None
    x_scale: Literal["linear", "log10", "ln", "log2"] | None = None
    y_scale: Literal["linear", "log10", "ln", "log2"] | None = None
    x_title: str | None = None
    y_title: str | None = None
    legend: bool | CategoricalLegendOptions | None = None
    rescale: bool | None = None
    plot_styles: list[PlotStyleOptions] | None = None
    data_binding: GraphDataBinding | None = None
    categorical_style: CategoricalStyleOptions | None = None


class WorksheetTransformOptions(StrictOptions):
    by: list[str] | None = None
    ascending: bool | list[bool] | None = None
    na_position: Literal["first", "last"] | None = None
    column: str | None = None
    operator: Literal[
        "eq", "ne", "gt", "ge", "lt", "le",
        "add", "subtract", "multiply", "divide", "power",
    ] | None = None
    value: Any | None = None
    subset: list[str] | None = None
    keep: Literal["first", "last", False] | None = None
    columns: str | list[str] | None = None
    strategy: Literal["value", "forward", "backward", "mean", "median", "drop_rows"] | None = None
    right_rows: list[list[Any]] | None = None
    right_columns: list[str] | None = None
    on: list[str] | None = None
    how: Literal["left", "right", "inner", "outer"] | None = None
    validation: Literal["one_to_one", "one_to_many", "many_to_one", "many_to_many"] | None = Field(
        default=None, alias="validate"
    )
    other_rows: list[list[Any]] | None = None
    other_columns: list[str] | None = None
    axis: Literal[0, 1] | None = None
    ignore_index: bool | None = None
    index: list[str] | None = None
    values: str | None = None
    aggregation: Literal["mean", "sum", "min", "max", "count", "median"] | None = None
    id_vars: list[str] | None = None
    value_vars: list[str] | None = None
    variable_name: str | None = None
    value_name: str | None = None
    name: str | None = None
    left: str | None = None
    right: str | None = None


def _inline_local_schema_refs(schema: dict[str, Any]) -> dict[str, Any]:
    definitions = schema.get("$defs", {})

    def expand(value: Any, stack: tuple[str, ...] = ()) -> Any:
        if isinstance(value, list):
            return [expand(item, stack) for item in value]
        if not isinstance(value, dict):
            return value
        ref = value.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            name = ref.rsplit("/", 1)[-1]
            if name not in stack and name in definitions:
                replacement = deepcopy(definitions[name])
                replacement.update({key: item for key, item in value.items() if key != "$ref"})
                return expand(replacement, (*stack, name))
        return {
            key: expand(item, stack)
            for key, item in value.items()
            if key != "$defs"
        }

    return expand(schema)


def create_server(
    *,
    controller: OriginController | None = None,
    controller_factory: Callable[[], OriginController] | None = None,
) -> FastMCP:
    initial_controller = controller or OriginController()
    factory = controller_factory or OriginController
    controller_box = {"active": initial_controller}
    workflow_tasks = TaskManager(max_results=100)

    def active_controller() -> OriginController:
        return controller_box["active"]

    registered_tools: list[Tool] = []

    def strict_tool(*, name: str):
        def register(function):
            tool = Tool.from_function(function, name=name)
            argument_model = tool.fn_metadata.arg_model
            argument_model.model_config = ConfigDict(
                **{**argument_model.model_config, "extra": "forbid"}
            )
            argument_model.model_rebuild(force=True)
            tool.parameters = argument_model.model_json_schema(by_alias=True)
            if name in {
                "origin_configure_graph",
                "origin_run_analysis",
                "origin_run_xfunction",
                "origin_transform_worksheet",
                "origin_plan_figure",
                "origin_execute_figure",
                "origin_submit_batch",
            }:
                tool.parameters = _inline_local_schema_refs(tool.parameters)
            registered_tools.append(tool)
            return function

        return register

    @strict_tool(name="origin_health_check")
    def origin_health_check() -> ResultEnvelope:
        """Inspect Origin registration, executable, Python bitness, and active processes without COM activation."""
        return health_check()

    @strict_tool(name="origin_capabilities")
    def origin_capabilities(
        domain: Literal[
            "session",
            "data",
            "connector",
            "matrix",
            "image",
            "analysis",
            "graph",
            "project",
            "workflow",
        ]
        | None = None,
    ) -> ResultEnvelope:
        """Report verified, supported-unverified, and unsupported Origin capabilities."""

        origin_version = getattr(active_controller(), "origin_version", None)
        return ResultEnvelope.ok(
            {
                "origin_version": origin_version,
                "capabilities": capability_report(origin_version, domain=domain),
            },
            origin_version=origin_version,
        )

    @strict_tool(name="origin_inspect_data_source")
    def origin_inspect_data_source(
        file_path: str,
        sheet_name: str | None = None,
        has_header: bool | None = None,
    ) -> ResultEnvelope:
        """Profile CSV, TSV, or Excel data without activating Origin."""

        try:
            return ResultEnvelope.ok(
                inspect_data_source(
                    file_path,
                    sheet_name=sheet_name,
                    has_header=has_header,
                )
            )
        except DataInspectionError as exc:
            return ResultEnvelope.fail("DATA_INSPECTION_FAILED", str(exc))

    @strict_tool(name="origin_graph_catalog")
    def origin_graph_catalog(
        family: Literal["2d", "statistical", "polar", "ternary", "matrix", "3d"] | None = None,
    ) -> ResultEnvelope:
        """List graph families, exact data roles, Origin mappings, and verification status."""
        return ResultEnvelope.ok({"graph_types": graph_catalog(family=family)})

    @strict_tool(name="origin_palette_catalog")
    def origin_palette_catalog() -> ResultEnvelope:
        """List plugin-owned scientific palettes with exact colors and usage restrictions."""
        return ResultEnvelope.ok({"palettes": palette_catalog()})

    @strict_tool(name="origin_list_graph_templates")
    def origin_list_graph_templates(roots: list[str]) -> ResultEnvelope:
        """Discover .otp/.otpu templates only beneath explicit template roots."""
        return ResultEnvelope.ok({"templates": discover_templates(roots), "roots": roots})

    @strict_tool(name="origin_inspect_png")
    def origin_inspect_png(
        path: str,
        expected_colors: list[HexColor] | None = None,
        tolerance: Annotated[int, Field(ge=0, le=255)] = 12,
    ) -> ResultEnvelope:
        """Measure PNG content, alpha coverage, bounding box, and expected-color pixels."""
        try:
            return ResultEnvelope.ok(
                inspect_png(path, expected_colors=expected_colors, tolerance=tolerance)
            )
        except (OSError, ValueError) as exc:
            return ResultEnvelope.fail("PNG_INSPECTION_FAILED", str(exc))

    @strict_tool(name="origin_query_knowledge")
    def origin_query_knowledge(
        term: str | None = None,
        domain: Literal[
            "analysis", "connector", "matrix", "image", "graph", "project", "workflow"
        ]
        | None = None,
        status: Literal["verified", "supported_unverified", "unsupported"] | None = None,
        limit: Annotated[int, Field(ge=1, le=100)] = 20,
    ) -> ResultEnvelope:
        """Query original local summaries linked to official Origin documentation."""
        try:
            results = query_knowledge(
                term=term, domain=domain, status=status, limit=limit
            )
        except ValueError as exc:
            return ResultEnvelope.fail("KNOWLEDGE_QUERY_INVALID", str(exc))
        return ResultEnvelope.ok({"results": results, "count": len(results)})

    @strict_tool(name="origin_start")
    def origin_start(
        progid: str | None = None,
        visible: bool | None = None,
        attach: bool | None = None,
        exclusive: bool = False,
    ) -> ResultEnvelope:
        """Create an owned Origin instance, or explicitly attach to an active one."""
        return active_controller().start(
            progid=progid, visible=visible, attach=attach, exclusive=exclusive
        )

    @strict_tool(name="origin_open_project")
    def origin_open_project(source_path: str, working_copy_path: str | None = None) -> ResultEnvelope:
        """Copy an OPJU project and open the copy in the active Origin session."""
        return active_controller().open_project(
            source_path=source_path, working_copy_path=working_copy_path
        )

    @strict_tool(name="origin_save_project_copy")
    def origin_save_project_copy(target_path: str, overwrite: bool = False) -> ResultEnvelope:
        """Save the active project to a separate validated OPJU output."""
        return active_controller().save_project_copy(target_path=target_path, overwrite=overwrite)

    @strict_tool(name="origin_save_and_replace_source")
    def origin_save_and_replace_source(
        source_path: str,
        expected_source_sha256: str,
        overwrite: bool = False,
        allow_source_overwrite: bool = False,
        keep_backup: bool = True,
    ) -> ResultEnvelope:
        """Replace the current protected source only after dual confirmation and candidate reopen validation."""
        return active_controller().save_and_replace_source(
            source_path=source_path,
            expected_source_sha256=expected_source_sha256,
            overwrite=overwrite,
            allow_source_overwrite=allow_source_overwrite,
            keep_backup=keep_backup,
        )

    @strict_tool(name="origin_list_objects")
    def origin_list_objects() -> ResultEnvelope:
        """List pages, layers, worksheet columns, and plot sources with reusable stable refs."""
        return active_controller().list_objects()

    @strict_tool(name="origin_import_data")
    def origin_import_data(
        file_path: str,
        worksheet_name: str | None = None,
        sheet_name: str | None = None,
        has_header: bool | None = None,
        target_mode: Literal["new_workbook", "existing_worksheet"] = "new_workbook",
        source_mode: Literal["linked", "snapshot"] = "linked",
    ) -> ResultEnvelope:
        """Import CSV, TSV, XLS, XLSX, or XLSM, with `has_header` true/false or automatic detection."""
        return active_controller().import_data(
            file_path=file_path,
            worksheet_name=worksheet_name,
            sheet_name=sheet_name,
            has_header=has_header,
            target_mode=target_mode,
            source_mode=source_mode,
        )

    @strict_tool(name="origin_transform_worksheet")
    def origin_transform_worksheet(
        source_ref: str,
        destination_ref: str,
        action: Literal[
            "sort",
            "filter",
            "deduplicate",
            "fill_missing",
            "transpose",
            "merge",
            "concat",
            "pivot",
            "melt",
            "calculated_column",
        ],
        options: WorksheetTransformOptions | None = None,
    ) -> ResultEnvelope:
        """Transform one worksheet into a distinct destination and verify exact readback."""
        return active_controller().transform_worksheet(
            source_ref=source_ref,
            destination_ref=destination_ref,
            action=action,
            options=options.model_dump(exclude_none=True, by_alias=True) if options else None,
        )

    @strict_tool(name="origin_manage_connector")
    def origin_manage_connector(
        action: Literal["create", "info", "refresh", "disconnect"],
        worksheet_ref: str,
        source: str | None = None,
        connector_type: Literal["csv", "excel"] | None = None,
        keep_connector: bool = True,
        keep_data: bool | None = None,
    ) -> ResultEnvelope:
        """Create, inspect, refresh, or explicitly disconnect a CSV/Excel Data Connector."""
        return active_controller().manage_connector(
            action=action,
            worksheet_ref=worksheet_ref,
            source=source,
            connector_type=connector_type,
            keep_connector=keep_connector,
            keep_data=keep_data,
        )

    @strict_tool(name="origin_manage_matrix")
    def origin_manage_matrix(
        action: Literal["create", "read", "write", "transform"],
        matrix_ref: str,
        values: list[list[float | None]] | None = None,
        row: Annotated[int, Field(ge=0)] = 0,
        column: Annotated[int, Field(ge=0)] = 0,
        operation: Literal[
            "transpose", "rotate_90", "flip_horizontal", "flip_vertical"
        ]
        | None = None,
    ) -> ResultEnvelope:
        """Read/write Matrix data or apply a closed transform operation."""
        return active_controller().manage_matrix(
            action=action,
            matrix_ref=matrix_ref,
            values=values,
            row=row,
            column=column,
            operation=operation,
        )

    @strict_tool(name="origin_manage_image")
    def origin_manage_image(
        action: Literal["create", "info", "import", "export", "delete"],
        image_ref: str,
        path: str | None = None,
        overwrite: bool = False,
    ) -> ResultEnvelope:
        """Create, inspect, import, export, or delete one stable Image Page ref."""
        return active_controller().manage_image(
            action=action,
            image_ref=image_ref,
            path=path,
            overwrite=overwrite,
        )

    @strict_tool(name="origin_read_worksheet")
    def origin_read_worksheet(
        name: str,
        r1: int = 0,
        c1: int = 0,
        r2: int = -1,
        c2: int = -1,
        data_format: Literal[
            "auto", "numeric", "string", "variant", "categorical_label"
        ] = "auto",
    ) -> ResultEnvelope:
        """Read a 0-based worksheet range as mixed values, numbers, text, or category labels."""
        return active_controller().read_worksheet(
            name,
            r1=r1,
            c1=c1,
            r2=r2,
            c2=c2,
            data_format=data_format,
        )

    @strict_tool(name="origin_write_worksheet")
    def origin_write_worksheet(
        name: str,
        values: list[list[Any]],
        row: int = 0,
        column: int = 0,
    ) -> ResultEnvelope:
        """Write a rectangular 2D array to a worksheet name or `[Book]Sheet` ref."""
        return active_controller().write_worksheet(name, values, row=row, column=column)

    @strict_tool(name="origin_run_analysis")
    def origin_run_analysis(
        worksheet_name: str,
        method: str,
        x_column: str | int,
        y_column: str | int,
        options: AnalysisOptions | None = None,
        row_start: int = 0,
        row_end: int = -1,
        filters: list[AnalysisFilter] | None = None,
        row_order: Literal["as_is", "reverse"] = "as_is",
    ) -> ResultEnvelope:
        """Analyze explicit columns/rows with AND filters and preserved as-is/reverse row order."""
        return active_controller().run_analysis(
            worksheet_name=worksheet_name,
            method=method,
            x_column=x_column,
            y_column=y_column,
            options=(options or AnalysisOptions()).model_dump(exclude_none=True),
            row_start=row_start,
            row_end=row_end,
            filters=[item.model_dump() for item in filters] if filters else None,
            row_order=row_order,
        )

    @strict_tool(name="origin_run_xfunction")
    def origin_run_xfunction(
        name: str,
        parameters: dict[str, NativeParameterInput],
        outputs: dict[str, NativeOutputInput] | None = None,
        create_operation: bool = False,
        recalculate_mode: Literal["none", "auto", "manual"] = "none",
        allow_unverified: bool = False,
    ) -> ResultEnvelope:
        """Run one validated X-Function with explicit typed parameters and outputs."""
        return active_controller().run_xfunction(
            name=name,
            parameters={
                key: _decode_native_parameter(value)
                for key, value in parameters.items()
            },
            outputs=(
                {key: OutputRef(value.value) for key, value in outputs.items()}
                if outputs
                else None
            ),
            create_operation=create_operation,
            recalculate_mode=recalculate_mode,
            allow_unverified=allow_unverified,
        )

    @strict_tool(name="origin_list_analysis_operations")
    def origin_list_analysis_operations(scope_ref: str | None = None) -> ResultEnvelope:
        """List only Analysis Operations created and tracked by this plugin session."""
        return active_controller().list_analysis_operations(scope_ref=scope_ref)

    @strict_tool(name="origin_get_analysis_operation")
    def origin_get_analysis_operation(operation_ref: str) -> ResultEnvelope:
        """Read native state for one stable plugin-managed Analysis Operation ref."""
        return active_controller().get_analysis_operation(operation_ref=operation_ref)

    @strict_tool(name="origin_recalculate_analysis")
    def origin_recalculate_analysis(
        operation_ref: str,
        wait: bool = True,
    ) -> ResultEnvelope:
        """Recalculate one plugin-managed native Analysis Operation without retrying mutation."""
        return active_controller().recalculate_analysis(
            operation_ref=operation_ref,
            wait=wait,
        )

    @strict_tool(name="origin_manage_analysis_template")
    def origin_manage_analysis_template(
        action: Literal["save", "load"],
        path: str,
        workbook_ref: str | None = None,
        overwrite: bool = False,
    ) -> ResultEnvelope:
        """Save or load an explicit Origin Analysis Template with path and overwrite checks."""
        return active_controller().manage_analysis_template(
            action=action,
            path=path,
            workbook_ref=workbook_ref,
            overwrite=overwrite,
        )

    @strict_tool(name="origin_execute_labtalk")
    def origin_execute_labtalk(
        script: str = "",
        segments: list[str] | None = None,
        result_variable: str | None = None,
        result_variables: list[str] | None = None,
        result_numeric_variables: list[str] | None = None,
        result_string_variables: list[str] | None = None,
        warning_variable: str | None = None,
    ) -> ResultEnvelope:
        """Execute one LabTalk script or explicit ordered segments and report the exact failing segment."""
        return active_controller().execute_labtalk(
            script=script,
            segments=segments,
            result_variable=result_variable,
            result_variables=result_variables,
            result_numeric_variables=result_numeric_variables,
            result_string_variables=result_string_variables,
            warning_variable=warning_variable,
        )

    @strict_tool(name="origin_create_plot")
    def origin_create_plot(
        worksheet_name: str,
        graph_type: str,
        x_column: str | int,
        y_columns: list[str | int],
        label_column: str | int | None = None,
        graph_name: str | None = None,
        options: CreatePlotOptions | None = None,
    ) -> ResultEnvelope:
        """Create a typed Origin graph from explicit X/Y columns and an optional label column."""
        return active_controller().create_plot(
            worksheet_name=worksheet_name,
            graph_type=graph_type,
            x_column=x_column,
            y_columns=y_columns,
            label_column=label_column,
            graph_name=graph_name,
            options=options.model_dump(exclude_none=True) if options else None,
        )

    @strict_tool(name="origin_create_graph")
    def origin_create_graph(
        graph_type: str,
        roles: dict[str, str | int | list[str | int]],
        graph_name: str | None = None,
        allow_unverified: bool = False,
    ) -> ResultEnvelope:
        """Create a catalog graph from explicit named roles; unverified types require opt-in."""
        return active_controller().create_graph(
            graph_type=graph_type,
            roles=roles,
            graph_name=graph_name,
            allow_unverified=allow_unverified,
        )

    @strict_tool(name="origin_manage_graph_layout")
    def origin_manage_graph_layout(
        action: Literal["add_layer", "grid", "inset", "dual_y", "link_axes", "merge", "extract"],
        graph_ref: str,
        source_graph_refs: list[str] | None = None,
        layer_refs: list[str] | None = None,
        position: list[float] | None = None,
        rows: Annotated[int, Field(ge=1)] | None = None,
        columns: Annotated[int, Field(ge=1)] | None = None,
    ) -> ResultEnvelope:
        """Manage layers, insets, dual-Y, grids, links, merges, and extraction."""
        return active_controller().manage_graph_layout(
            action=action,
            graph_ref=graph_ref,
            source_graph_refs=source_graph_refs,
            layer_refs=layer_refs,
            position=position,
            rows=rows,
            columns=columns,
        )

    @strict_tool(name="origin_apply_graph_template")
    def origin_apply_graph_template(
        graph_ref: str,
        template_path: str,
        expected_sha256: str,
        required_layers: Annotated[int, Field(ge=1)] | None = None,
    ) -> ResultEnvelope:
        """Apply one explicit digest-locked graph template after layer compatibility checks."""
        return active_controller().apply_graph_template(
            graph_ref=graph_ref,
            template_path=template_path,
            expected_sha256=expected_sha256,
            required_layers=required_layers,
        )

    @strict_tool(name="origin_view_graph")
    def origin_view_graph(
        graph_name: str,
        output_path: str | None = None,
        expected_colors: list[HexColor] | None = None,
        tolerance: Annotated[int, Field(ge=0, le=255)] = 12,
    ) -> list[TextContent | ImageContent]:
        """Export a graph preview and return pixel QA metrics and the PNG artifact path."""
        result = active_controller().view_graph(
            graph_name=graph_name,
            output_path=output_path,
            expected_colors=expected_colors,
            tolerance=tolerance,
        )
        content: list[TextContent | ImageContent] = [
            TextContent(
                type="text",
                text=json.dumps(result.to_dict(), ensure_ascii=False),
            )
        ]
        preview_path = (result.data or {}).get("preview_path") if result.success else None
        if preview_path:
            path = Path(preview_path).expanduser().resolve()
            if path.is_file() and path.suffix.lower() == ".png":
                content.append(
                    ImageContent(
                        type="image",
                        data=base64.b64encode(path.read_bytes()).decode("ascii"),
                        mimeType="image/png",
                    )
                )
        return content

    @strict_tool(name="origin_configure_graph")
    def origin_configure_graph(
        graph_name: str,
        options: GraphConfigurationOptions,
        labtalk: str | None = None,
    ) -> ResultEnvelope:
        """Configure axes, binding, categorical markers and legend, or explicit LabTalk."""
        return active_controller().configure_graph(
            graph_name=graph_name,
            options=options.model_dump(exclude_none=True),
            labtalk=labtalk,
        )

    @strict_tool(name="origin_export_graph")
    def origin_export_graph(
        graph_name: str,
        output_path: str,
        export_format: str,
        overwrite: str = "skip",
    ) -> ResultEnvelope:
        """Export one named graph with an explicit non-interactive overwrite policy and validate the artifact."""
        return active_controller().export_graph(
            graph_name=graph_name,
            output_path=output_path,
            export_format=export_format,
            overwrite=overwrite,
        )

    @strict_tool(name="origin_plan_figure")
    def origin_plan_figure(spec: FigureSpec) -> ResultEnvelope:
        """Preflight a declarative figure route and return its immutable execution digest."""
        controller = active_controller()
        version = getattr(controller, "origin_version", None) or getattr(
            controller, "_origin_version", None
        )
        return ResultEnvelope.ok(
            compile_figure_spec(spec, origin_version=version),
            origin_version=version,
        )

    @strict_tool(name="origin_execute_figure")
    def origin_execute_figure(spec: FigureSpec, plan_digest: str) -> ResultEnvelope:
        """Submit one digest-approved FigureSpec to the serialized background workflow queue."""
        actual_digest = figure_spec_digest(spec)
        if actual_digest != plan_digest:
            return ResultEnvelope.fail(
                "FIGURE_PLAN_CHANGED",
                "FigureSpec no longer matches the approved plan digest",
                data={"expected_digest": plan_digest, "actual_digest": actual_digest},
            )
        controller = active_controller()
        version = getattr(controller, "origin_version", None) or getattr(
            controller, "_origin_version", None
        )
        plan = compile_figure_spec(spec, origin_version=version)
        if not plan["executor_executable"]:
            return ResultEnvelope.fail(
                "FIGURE_PREFLIGHT_BLOCKED",
                "; ".join(plan["blockers"]),
                data=plan,
            )
        task_id = workflow_tasks.submit(
            f"figure:{spec.route}",
            lambda context: execute_figure(
                active_controller(),
                spec,
                expected_digest=plan_digest,
                context=context,
            ),
        )
        return ResultEnvelope.ok(
            {
                "task_id": task_id,
                "state": "queued",
                "plan_digest": plan_digest,
                "next_tool": "origin_task_status",
            },
            origin_version=version,
        )

    @strict_tool(name="origin_submit_batch")
    def origin_submit_batch(
        specs: list[FigureSpec],
        plan_digests: list[str],
        on_error: Literal["stop", "continue"] = "stop",
    ) -> ResultEnvelope:
        """Submit explicit FigureSpecs for one-at-a-time execution with no replay."""
        if not specs or len(specs) != len(plan_digests):
            return ResultEnvelope.fail(
                "BATCH_PLAN_INVALID",
                "specs and plan_digests must be non-empty and have equal length",
            )
        for index, (spec, digest) in enumerate(zip(specs, plan_digests, strict=True)):
            if figure_spec_digest(spec) != digest:
                return ResultEnvelope.fail(
                    "BATCH_PLAN_CHANGED",
                    f"Batch FigureSpec {index} does not match its approved digest",
                )
            version = getattr(active_controller(), "_origin_version", None)
            plan = compile_figure_spec(spec, origin_version=version)
            if not plan["executor_executable"]:
                return ResultEnvelope.fail(
                    "BATCH_PREFLIGHT_BLOCKED",
                    f"Batch FigureSpec {index}: {'; '.join(plan['blockers'])}",
                    data={"index": index, "plan": plan},
                )

        def execute_serial(context):
            results = []
            for index, (spec, digest) in enumerate(zip(specs, plan_digests, strict=True)):
                result = execute_figure(
                    active_controller(),
                    spec,
                    expected_digest=digest,
                    context=context,
                )
                results.append({"index": index, "result": result})
                if not result.get("success", False) and on_error == "stop":
                    break
            return {
                "success": all(item["result"].get("success", False) for item in results),
                "total": len(specs),
                "completed": len(results),
                "stopped_early": len(results) < len(specs),
                "results": results,
            }

        task_id = workflow_tasks.submit("batch", execute_serial)
        return ResultEnvelope.ok(
            {
                "task_id": task_id,
                "state": "queued",
                "items": len(specs),
                "on_error": on_error,
                "next_tool": "origin_task_status",
            }
        )

    @strict_tool(name="origin_task_status")
    def origin_task_status(task_id: str) -> ResultEnvelope:
        """Read queued/running/terminal workflow state and completed stages."""
        try:
            return ResultEnvelope.ok(workflow_tasks.status(task_id))
        except KeyError:
            return ResultEnvelope.fail("TASK_NOT_FOUND", f"Workflow task not found: {task_id}")

    @strict_tool(name="origin_cancel_task")
    def origin_cancel_task(task_id: str) -> ResultEnvelope:
        """Cancel only a pending workflow; active Origin mutations are never interrupted."""
        try:
            status = workflow_tasks.cancel(task_id)
        except KeyError:
            return ResultEnvelope.fail("TASK_NOT_FOUND", f"Workflow task not found: {task_id}")
        if status.get("error_code"):
            return ResultEnvelope.fail(
                status["error_code"], status["error_message"], data=status
            )
        return ResultEnvelope.ok(status)

    @strict_tool(name="origin_manage_project_folder")
    def origin_manage_project_folder(
        action: Literal["list", "create", "move", "rename", "delete"],
        path: str,
        destination: str | None = None,
        confirm_recursive: bool = False,
    ) -> ResultEnvelope:
        """List or mutate full Project Explorer paths with recursive-delete confirmation."""
        return active_controller().manage_project_folder(
            action=action,
            path=path,
            destination=destination,
            confirm_recursive=confirm_recursive,
        )

    @strict_tool(name="origin_manage_note")
    def origin_manage_note(
        action: Literal["info", "create", "write", "export", "delete"],
        note_ref: str,
        text: str | None = None,
        format: Literal["text", "html"] = "text",
        path: str | None = None,
        overwrite: bool = False,
    ) -> ResultEnvelope:
        """Inspect, write, export, or delete an Origin Notes page by stable ref."""
        return active_controller().manage_note(
            action=action,
            note_ref=note_ref,
            text=text,
            format=format,
            path=path,
            overwrite=overwrite,
        )

    @strict_tool(name="origin_close_project")
    def origin_close_project(discard_changes: bool = False) -> ResultEnvelope:
        """Close the active project by opening a new blank project, refusing unsaved changes by default."""
        return active_controller().close_project(discard_changes=discard_changes)

    @strict_tool(name="origin_recover_session")
    def origin_recover_session() -> ResultEnvelope:
        """Replace a controller whose STA worker timed out, without queuing onto the blocked worker."""
        previous = active_controller()
        abandoned = previous.abandon_poisoned_session()
        if not abandoned.success:
            return abandoned
        controller_box["active"] = factory()
        return ResultEnvelope.ok(
            {
                **(abandoned.data or {}),
                "controller_replaced": True,
                "new_controller_ready": True,
                "next_step": "origin_start",
            },
            warnings=abandoned.warnings,
            duration_ms=abandoned.duration_ms,
            origin_version=abandoned.origin_version,
        )

    @strict_tool(name="origin_shutdown")
    def origin_shutdown() -> ResultEnvelope:
        """Shut down only a plugin-owned Origin instance, or detach from a user-owned instance."""
        return active_controller().shutdown()

    return FastMCP(
        "Origin COM Automation",
        json_response=True,
        tools=registered_tools,
    )


def main() -> None:
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
