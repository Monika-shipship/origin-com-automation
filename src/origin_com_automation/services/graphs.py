"""Validated graph specifications shared by COM and LabTalk adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SUPPORTED_GRAPH_TYPES = {"scatter", "line", "semilog", "loglog", "bar", "multi_layer"}


@dataclass(frozen=True)
class GraphSpec:
    graph_type: str
    x_column: str
    y_columns: list[str]
    options: dict[str, Any] = field(default_factory=dict)


def build_graph_spec(
    *,
    graph_type: str,
    x_column: str,
    y_columns: list[str],
    options: dict[str, Any] | None = None,
) -> GraphSpec:
    if graph_type not in SUPPORTED_GRAPH_TYPES:
        raise ValueError(f"Unsupported Origin graph type: {graph_type}")
    if not x_column.strip() or not y_columns or any(not column.strip() for column in y_columns):
        raise ValueError("x_column and at least one non-empty y_column are required")
    normalized_options = dict(options or {})
    unknown = sorted(set(normalized_options) - {"template"})
    if unknown:
        raise ValueError(f"Unsupported plot creation options: {', '.join(unknown)}")
    if "template" in normalized_options and not str(normalized_options["template"]).strip():
        raise ValueError("template must be a non-empty Origin template name")
    return GraphSpec(graph_type, x_column, list(y_columns), normalized_options)
