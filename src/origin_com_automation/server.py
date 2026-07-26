"""FastMCP stdio server for safe Origin automation."""

from __future__ import annotations

import logging
import sys
from copy import deepcopy
from collections.abc import Callable
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.tools import Tool
from pydantic import BaseModel, ConfigDict, Field

from .com.origin_api import OriginController
from .contracts import ResultEnvelope
from .tools.health import health_check

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


class StrictOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnalysisOptions(StrictOptions):
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
            if name == "origin_configure_graph":
                tool.parameters = _inline_local_schema_refs(tool.parameters)
            registered_tools.append(tool)
            return function

        return register

    @strict_tool(name="origin_health_check")
    def origin_health_check() -> ResultEnvelope:
        """Inspect Origin registration, executable, Python bitness, and active processes without COM activation."""
        return health_check()

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
    ) -> ResultEnvelope:
        """Import CSV, TSV, XLS, XLSX, or XLSM, with `has_header` true/false or automatic detection."""
        return active_controller().import_data(
            file_path=file_path,
            worksheet_name=worksheet_name,
            sheet_name=sheet_name,
            has_header=has_header,
            target_mode=target_mode,
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
            options=options.model_dump(exclude_none=True) if options else None,
            row_start=row_start,
            row_end=row_end,
            filters=[item.model_dump() for item in filters] if filters else None,
            row_order=row_order,
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
