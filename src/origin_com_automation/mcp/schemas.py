"""Strict Pydantic input schemas used by the Origin MCP tools."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field

from ..utils.runtime import StrictModel


class StrictOptions(StrictModel):
    pass


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
    execution_mode: Literal["origin_native", "materialized"] = "origin_native"
    before_script: str = ""
    row_start: Annotated[int, Field(ge=0)] = 0
    row_end: Annotated[int, Field(ge=-1)] = -1
    recalculate_mode: Literal["none", "auto", "manual"] = "auto"
