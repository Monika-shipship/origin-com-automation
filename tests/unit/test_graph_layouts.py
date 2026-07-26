import pytest

from origin_com_automation.graphs.layout import GraphLayoutError, build_layout_plan


def test_inset_and_dual_y_layouts_have_bounded_positions():
    inset = build_layout_plan(
        action="inset",
        graph_ref="Graph1",
        source_graph_refs=["Graph2"],
        position=[0.58, 0.55, 0.95, 0.93],
    )
    assert inset.expected_layer_delta == 1
    assert inset.position == (0.58, 0.55, 0.95, 0.93)
    dual = build_layout_plan(action="dual_y", graph_ref="Graph1")
    assert "layer -y" in dual.command


def test_layout_rejects_invalid_position_and_duplicate_sources():
    with pytest.raises(GraphLayoutError, match="position"):
        build_layout_plan(
            action="inset", graph_ref="Graph1", source_graph_refs=["Graph2"], position=[0.8, 0.2, 0.1, 0.9]
        )
    with pytest.raises(GraphLayoutError, match="unique"):
        build_layout_plan(
            action="merge", graph_ref="Graph1", source_graph_refs=["Graph2", "Graph2"]
        )


def test_grid_layout_requires_explicit_capacity():
    plan = build_layout_plan(
        action="grid", graph_ref="Graph1", rows=2, columns=2, layer_refs=["1", "2", "3"]
    )
    assert plan.rows == 2 and plan.columns == 2
    with pytest.raises(GraphLayoutError, match="capacity"):
        build_layout_plan(
            action="grid", graph_ref="Graph1", rows=1, columns=2, layer_refs=["1", "2", "3"]
        )

