"""Closed graph layer and multi-panel layout plans."""

from __future__ import annotations

from dataclasses import dataclass

from ..objects.validation import stable_ref


class GraphLayoutError(ValueError):
    code = "GRAPH_LAYOUT_INVALID"


@dataclass(frozen=True)
class LayoutPlan:
    action: str
    graph_ref: str
    source_graph_refs: tuple[str, ...]
    layer_refs: tuple[str, ...]
    position: tuple[float, float, float, float] | None
    rows: int | None
    columns: int | None
    command: str
    expected_layer_delta: int


def build_layout_plan(
    *,
    action: str,
    graph_ref: str,
    source_graph_refs: list[str] | None = None,
    layer_refs: list[str] | None = None,
    position: list[float] | None = None,
    rows: int | None = None,
    columns: int | None = None,
) -> LayoutPlan:
    normalized = action.strip().lower()
    if normalized not in {"add_layer", "grid", "inset", "dual_y", "link_axes", "merge", "extract"}:
        raise GraphLayoutError("unsupported graph layout action")
    target = stable_ref(graph_ref, kind="graph ref")
    sources = tuple(stable_ref(item, kind="source graph ref") for item in (source_graph_refs or []))
    if len(set(sources)) != len(sources):
        raise GraphLayoutError("source graph refs must be unique")
    layers = tuple(stable_ref(item, kind="layer ref") for item in (layer_refs or []))
    normalized_position = None
    if position is not None:
        if len(position) != 4:
            raise GraphLayoutError("position must contain left, top, right, bottom")
        normalized_position = tuple(float(value) for value in position)
        left, top, right, bottom = normalized_position
        if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
            raise GraphLayoutError("position must be ordered inside normalized page bounds")
    if normalized == "inset":
        if len(sources) != 1 or normalized_position is None:
            raise GraphLayoutError("inset requires one source graph and position")
        command = f"layer -i {sources[0]};"
        delta = 1
    elif normalized == "dual_y":
        command = "layer -y;"
        delta = 1
    elif normalized == "grid":
        if not rows or not columns or rows < 1 or columns < 1:
            raise GraphLayoutError("grid requires positive rows and columns")
        if len(layers) > rows * columns:
            raise GraphLayoutError("grid capacity is smaller than the layer count")
        command = f"layarrange row:={rows} col:={columns};"
        delta = 0
    elif normalized == "merge":
        if not sources:
            raise GraphLayoutError("merge requires source graph refs")
        command = "merge_graph;"
        delta = len(sources)
    elif normalized == "add_layer":
        command = "layer -n;"
        delta = 1
    elif normalized == "link_axes":
        command = "layer -l;"
        delta = 0
    else:
        command = "layer -e;"
        delta = -1
    return LayoutPlan(
        action=normalized,
        graph_ref=target,
        source_graph_refs=sources,
        layer_refs=layers,
        position=normalized_position,
        rows=rows,
        columns=columns,
        command=command,
        expected_layer_delta=delta,
    )

