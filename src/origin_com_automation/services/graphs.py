"""Validated graph specifications shared by COM and LabTalk adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..graphs.catalog import graph_catalog, validate_graph_request


SUPPORTED_GRAPH_TYPES = frozenset(graph_catalog())


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
    if not x_column.strip() or not y_columns or any(not column.strip() for column in y_columns):
        raise ValueError("x_column and at least one non-empty y_column are required")
    try:
        validate_graph_request(graph_type, {"x": x_column, "y": y_columns})
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    normalized_options = dict(options or {})
    unknown = sorted(set(normalized_options) - {"template"})
    if unknown:
        raise ValueError(f"Unsupported plot creation options: {', '.join(unknown)}")
    if "template" in normalized_options and not str(normalized_options["template"]).strip():
        raise ValueError("template must be a non-empty Origin template name")
    return GraphSpec(graph_type, x_column, list(y_columns), normalized_options)
