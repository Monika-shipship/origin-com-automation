"""Stateless graph reference, validation, and LabTalk command helpers."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .project_support import collection_items, labtalk_quote, safe_attr

GRAPH_OPTION_KEYS = {
    "x_min", "x_max", "y_min", "y_max", "x_tick_step", "y_tick_step",
    "x_scale", "y_scale", "x_title", "y_title", "legend", "rescale",
    "plot_styles", "data_binding", "categorical_style",
}
SCALE_TYPES = {"linear": 0, "log10": 2, "ln": 8, "log2": 9}
LINE_CONNECTIONS = {
    "none": 0,
    "straight": 1,
    "two_point_segment": 2,
    "three_point_segment": 3,
    "b_spline": 8,
    "spline": 9,
    "step_horizontal": 11,
    "step_vertical": 12,
    "step_horizontal_center": 13,
    "step_vertical_center": 14,
    "bezier": 15,
}
DATA_BINDING_PLOT_TYPES = {"line": 200, "scatter": 201, "line_symbol": 202, "bar": 203}
CATEGORY_SHAPES = {
    "square": 1,
    "circle": 2,
    "triangle_up": 3,
    "triangle_down": 4,
    "diamond": 5,
    "hexagon": 6,
    "star": 7,
    "cross": 8,
    "x": 9,
}
CATEGORY_FILLS = {"solid": 0, "open": 1, "hollow": 3}


def graph_reference(app: Any, identifier: str) -> str:
    if not identifier.startswith("graph_page:"):
        return identifier
    parts = identifier.split(":", 2)
    if len(parts) == 2:
        return parts[1]
    page_name, layer_name = parts[1], parts[2]
    match = re.search(r"(\d+)$", layer_name)
    if match:
        return f"[{page_name}]{int(match.group(1))}"
    try:
        page = app.GraphPages.Item(page_name)
        for position, layer in enumerate(collection_items(safe_attr(page, "Layers")), start=1):
            if str(safe_attr(layer, "Name", "")) == layer_name:
                return f"[{page_name}]{position}"
    except Exception:
        pass
    return identifier


def graph_page_name(identifier: str) -> str:
    if identifier.startswith("[") and "]" in identifier:
        return identifier[1:].split("]", 1)[0]
    if identifier.startswith("graph_page:"):
        return identifier.split(":", 2)[1]
    return identifier


def resolve_graph_layer(app: Any, identifier: str) -> Any:
    reference = graph_reference(app, identifier)
    layer = app.FindGraphLayer(reference)
    if layer is None:
        raise LookupError(f"Origin graph layer not found: {identifier}")
    return layer


def graph_configuration_commands(options: Mapping[str, Any], labtalk: str | None) -> list[str]:
    unknown = sorted(set(options) - GRAPH_OPTION_KEYS)
    if unknown:
        raise ValueError(f"Unsupported graph options: {', '.join(unknown)}")
    commands: list[str] = []
    for axis in ("x", "y"):
        if f"{axis}_min" in options:
            commands.append(f"layer.{axis}.from={float(options[f'{axis}_min'])};")
        if f"{axis}_max" in options:
            commands.append(f"layer.{axis}.to={float(options[f'{axis}_max'])};")
        if f"{axis}_tick_step" in options:
            step = float(options[f"{axis}_tick_step"])
            if step <= 0:
                raise ValueError(f"{axis}_tick_step must be positive")
            commands.append(f"layer.{axis}.inc={step};")
        if f"{axis}_scale" in options:
            scale = str(options[f"{axis}_scale"]).lower()
            if scale not in SCALE_TYPES:
                raise ValueError(f"{axis}_scale must be linear, log10, ln, or log2")
            commands.append(f"layer.{axis}.type={SCALE_TYPES[scale]};")
        if f"{axis}_title" in options:
            flag = "xb" if axis == "x" else "yl"
            commands.append(f"label -{flag} {labtalk_quote(str(options[f'{axis}_title']))};")
    if options.get("rescale"):
        commands.append("rescale;")
    if options.get("legend") is True:
        commands.append("legend;")
    elif options.get("legend") is False:
        commands.append("legend -d;")
    styles = options.get("plot_styles", [])
    if not isinstance(styles, list):
        raise ValueError("plot_styles must be a list")
    for style in styles:
        if not isinstance(style, Mapping):
            raise ValueError("Each plot_styles entry must be an object")
        unknown_style = sorted(set(style) - {"plot_index", "color_index", "line_connection"})
        if unknown_style:
            raise ValueError(f"Unsupported plot style options: {', '.join(unknown_style)}")
        plot_index = int(style.get("plot_index", 1))
        if plot_index < 1:
            raise ValueError("plot_index must be 1 or greater")
        dataset = f"%({plot_index},@D)"
        if "color_index" in style:
            color_index = int(style["color_index"])
            if color_index < 0:
                raise ValueError("color_index must be non-negative")
            commands.append(f"set {dataset} -c {color_index};")
        if "line_connection" in style:
            raw_connection = style["line_connection"]
            if isinstance(raw_connection, str):
                connection_name = raw_connection.lower()
                if connection_name not in LINE_CONNECTIONS:
                    raise ValueError(f"Unsupported line_connection: {raw_connection}")
                connection = LINE_CONNECTIONS[connection_name]
            else:
                connection = int(raw_connection)
            commands.append(f"set {dataset} -l {connection};")
    if labtalk:
        commands.append(labtalk)
    return commands


def normalize_graph_data_binding(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("data_binding must be an object")
    unknown = sorted(set(value) - {"worksheet_name", "x_column", "y_columns", "label_column", "plot_type"})
    if unknown:
        raise ValueError(f"Unsupported data_binding fields: {', '.join(unknown)}")
    worksheet_name = str(value.get("worksheet_name", "")).strip()
    y_columns = list(value.get("y_columns") or [])
    plot_type = str(value.get("plot_type", "line")).lower()
    if not worksheet_name or "x_column" not in value or not y_columns:
        raise ValueError("data_binding requires worksheet_name, x_column, and at least one y_column")
    if plot_type not in DATA_BINDING_PLOT_TYPES:
        raise ValueError("data_binding plot_type must be line, scatter, line_symbol, or bar")
    normalized = {
        "worksheet_name": worksheet_name,
        "x_column": value["x_column"],
        "y_columns": y_columns,
        "plot_type": plot_type,
    }
    if value.get("label_column") is not None:
        normalized["label_column"] = value["label_column"]
    return normalized


def normalize_categorical_style(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("categorical_style must be an object")
    unknown = sorted(set(value) - {"plot_index", "worksheet_name", "category_column", "categories"})
    if unknown:
        raise ValueError(f"Unsupported categorical_style fields: {', '.join(unknown)}")
    if "category_column" not in value:
        raise ValueError("categorical_style requires category_column")
    plot_index = int(value.get("plot_index", 1))
    if plot_index < 1:
        raise ValueError("categorical_style plot_index must be 1 or greater")
    worksheet_name = str(value.get("worksheet_name", "")).strip() or None
    raw_categories = value.get("categories")
    if not isinstance(raw_categories, Mapping) or not raw_categories:
        raise ValueError("categorical_style categories must be a non-empty object")
    categories: dict[str, dict[str, Any]] = {}
    for raw_category, raw_style in raw_categories.items():
        category = str(raw_category)
        if not category:
            raise ValueError("categorical_style category names must not be empty")
        if not isinstance(raw_style, Mapping):
            raise ValueError(f"Style for category {category!r} must be an object")
        unknown_style = sorted(set(raw_style) - {"color", "shape", "fill", "size"})
        if unknown_style:
            raise ValueError(f"Unsupported style fields for category {category!r}: {', '.join(unknown_style)}")
        style: dict[str, Any] = {}
        if "color" in raw_style:
            color = str(raw_style["color"]).strip()
            if not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
                raise ValueError(f"Category {category!r} color must use #RRGGBB")
            style["color"] = color.upper()
        if "shape" in raw_style:
            shape = str(raw_style["shape"]).strip().lower()
            if shape not in CATEGORY_SHAPES:
                raise ValueError(f"Category {category!r} shape must be one of: {', '.join(CATEGORY_SHAPES)}")
            style["shape"] = shape
        if "fill" in raw_style:
            fill = str(raw_style["fill"]).strip().lower()
            if fill not in CATEGORY_FILLS:
                raise ValueError(f"Category {category!r} fill must be one of: {', '.join(CATEGORY_FILLS)}")
            style["fill"] = fill
        if "size" in raw_style:
            size = float(raw_style["size"])
            if size <= 0:
                raise ValueError(f"Category {category!r} size must be positive")
            style["size"] = size
        if not style:
            raise ValueError(f"Style for category {category!r} must set at least one property")
        categories[category] = style
    return {
        "plot_index": plot_index,
        "worksheet_name": worksheet_name,
        "category_column": value["category_column"],
        "categories": categories,
    }


def normalize_categorical_legend(value: Any) -> dict[str, Any] | None:
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, Mapping):
        raise ValueError("legend must be true, false, or an object")
    allowed = {
        "mode", "source", "plot_index", "position", "font_size", "line_spacing",
        "border", "background", "replace_existing", "show_all_categories",
    }
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValueError(f"Unsupported categorical legend fields: {', '.join(unknown)}")
    mode = str(value.get("mode", "categorical")).lower()
    source = str(value.get("source", "plot_style_mapping")).lower()
    position = str(value.get("position", "top_right")).lower()
    background = str(value.get("background", "transparent")).lower()
    if mode != "categorical":
        raise ValueError("Structured legend mode must be categorical")
    if source != "plot_style_mapping":
        raise ValueError("Categorical legend source must be plot_style_mapping")
    if position != "top_right":
        raise ValueError("Only the verified categorical legend position top_right is supported")
    if background != "transparent":
        raise ValueError("Only the verified categorical legend background transparent is supported")
    plot_index = int(value.get("plot_index", 1))
    if plot_index < 1:
        raise ValueError("legend plot_index must be 1 or greater")
    font_size = value.get("font_size")
    if font_size is not None and float(font_size) <= 0:
        raise ValueError("legend font_size must be positive")
    line_spacing = value.get("line_spacing")
    if line_spacing is not None and float(line_spacing) <= 0:
        raise ValueError("legend line_spacing must be positive")
    border = value.get("border", False)
    replace_existing = value.get("replace_existing", True)
    show_all = value.get("show_all_categories", False)
    if not isinstance(border, bool):
        raise ValueError("legend border must be true or false")
    if not isinstance(replace_existing, bool):
        raise ValueError("legend replace_existing must be true or false")
    if not isinstance(show_all, bool):
        raise ValueError("legend show_all_categories must be true or false")
    return {
        "mode": mode,
        "source": source,
        "plot_index": plot_index,
        "position": position,
        "font_size": None if font_size is None else float(font_size),
        "line_spacing": None if line_spacing is None else float(line_spacing),
        "border": border,
        "background": background,
        "replace_existing": replace_existing,
        "show_all_categories": show_all,
    }
