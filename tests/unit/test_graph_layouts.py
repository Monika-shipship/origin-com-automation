import pytest

from origin_com_automation.graphs.layout import GraphLayoutError, build_layout_plan, plan_graph_presentation


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


def test_presentation_policy_scales_legend_ticks_and_margins():
    compact = plan_graph_presentation(curve_count=3, label_lengths=[4, 6, 5], scientific_axis=False)
    dense = plan_graph_presentation(curve_count=18, label_lengths=[22] * 18, scientific_axis=True)
    assert compact.legend_columns == 1
    assert dense.legend_columns > compact.legend_columns
    assert dense.major_tick_target < compact.major_tick_target
    assert dense.right_margin > compact.right_margin
    assert len(dense.palette) >= 8
    assert {"circle", "square", "star", "hexagon", "cross"} <= set(dense.markers)
