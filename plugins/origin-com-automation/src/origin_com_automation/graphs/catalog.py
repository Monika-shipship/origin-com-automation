"""Stable graph families and their explicit input roles."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


class GraphCatalogError(ValueError):
    code = "GRAPH_CATALOG_INVALID"


@dataclass(frozen=True)
class GraphType:
    graph_id: str
    family: str
    required_roles: tuple[str, ...]
    optional_roles: tuple[str, ...]
    input_kind: str
    plot_id: int | None
    template: str | None
    status: str


GRAPH_TYPES = (
    GraphType("scatter", "2d", ("x", "y"), ("label", "worksheet"), "worksheet", 201, None, "verified"),
    GraphType("line", "2d", ("x", "y"), ("worksheet",), "worksheet", 200, None, "verified"),
    GraphType("line_symbol", "2d", ("x", "y"), ("label", "worksheet"), "worksheet", 202, None, "verified"),
    GraphType("bar", "2d", ("x", "y"), ("worksheet",), "worksheet", 203, None, "verified"),
    GraphType("area", "2d", ("x", "y"), ("worksheet",), "worksheet", None, "Area", "supported_unverified"),
    GraphType("histogram", "statistical", ("y",), ("worksheet",), "worksheet", 219, None, "supported_unverified"),
    GraphType("box", "statistical", ("y",), ("group", "worksheet"), "worksheet", None, "Box", "supported_unverified"),
    GraphType("violin", "statistical", ("y",), ("group", "worksheet"), "worksheet", None, "Violin", "supported_unverified"),
    GraphType("probability", "statistical", ("y",), ("worksheet",), "worksheet", None, "Probability", "supported_unverified"),
    GraphType("polar", "polar", ("angle", "radius"), ("worksheet",), "worksheet", 225, None, "supported_unverified"),
    GraphType("ternary", "ternary", ("a", "b", "c"), ("worksheet",), "worksheet", None, "Ternary", "supported_unverified"),
    GraphType("vector", "2d", ("x", "y", "u", "v"), ("worksheet",), "worksheet", None, "Vector", "supported_unverified"),
    GraphType("bubble", "2d", ("x", "y", "size"), ("color", "worksheet"), "worksheet", None, "Bubble", "supported_unverified"),
    GraphType("contour", "matrix", ("z",), (), "matrix", 226, None, "supported_unverified"),
    GraphType("heatmap", "matrix", ("z",), (), "matrix", 105, None, "supported_unverified"),
    GraphType("surface_3d", "3d", ("z",), (), "matrix", 103, None, "supported_unverified"),
    GraphType("scatter_3d", "3d", ("x", "y", "z"), ("worksheet",), "worksheet", 101, None, "supported_unverified"),
    GraphType("waterfall_3d", "3d", ("x", "y", "z"), ("worksheet",), "worksheet", None, "Waterfall", "supported_unverified"),
)


def graph_catalog(*, family: str | None = None) -> dict[str, dict[str, Any]]:
    selected = GRAPH_TYPES if family is None else tuple(item for item in GRAPH_TYPES if item.family == family)
    return {
        item.graph_id: {
            **asdict(item),
            "required_roles": list(item.required_roles),
            "optional_roles": list(item.optional_roles),
        }
        for item in selected
    }


def validate_graph_request(graph_id: str, roles: Mapping[str, Any]) -> dict[str, Any]:
    spec = next((item for item in GRAPH_TYPES if item.graph_id == graph_id), None)
    if spec is None:
        raise GraphCatalogError(f"unknown graph type: {graph_id}")
    provided = set(roles)
    missing = sorted(set(spec.required_roles) - provided)
    if missing:
        raise GraphCatalogError(f"missing roles for {graph_id}: {', '.join(missing)}")
    unsupported = sorted(provided - set(spec.required_roles) - set(spec.optional_roles))
    if unsupported:
        raise GraphCatalogError(f"unsupported roles for {graph_id}: {', '.join(unsupported)}")
    if any(value is None or str(value).strip() == "" for value in roles.values()):
        raise GraphCatalogError("graph role references must be non-empty")
    return graph_catalog()[graph_id]
