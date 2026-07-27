import pytest

from origin_com_automation.workflows.selections import (
    SelectionPlanError,
    compile_selection,
)


def test_discontinuous_ranges_preserve_explicit_order_and_missing_rule():
    plan = compile_selection(
        ranges=[(0, 4), (10, 12)],
        order="reverse",
        branch="explicit",
        filters=[{"column": "C", "operator": ">", "value": 0}],
        missing_rule="exclude",
    )

    assert plan.ranges == ((0, 4), (10, 12))
    assert plan.order == "reverse"
    assert plan.filters[0]["operator"] == ">"
    assert plan.missing_rule == "exclude"
    assert plan.requires_helper is True
    assert plan.helper is not None
    assert plan.helper.logical_id.startswith("helper:__codex_")
    assert plan.helper.workbook_ref == "[__CodexWorkflow]Selections"
    assert plan.helper.cleanup_targets == (plan.helper.logical_id,)


def test_category_branch_requires_column_and_values():
    with pytest.raises(SelectionPlanError, match="category_column"):
        compile_selection(ranges=[], order="input", branch="category")

    plan = compile_selection(
        ranges=[],
        order="input",
        branch="category",
        category_column="D",
        category_values=["forward", "reverse"],
    )
    assert plan.category_column == "D"
    assert plan.category_values == ("forward", "reverse")


def test_selection_rejects_overlap_unknown_filter_and_user_cleanup_target():
    with pytest.raises(SelectionPlanError, match="overlap"):
        compile_selection(
            ranges=[(0, 5), (5, 8)], order="input", branch="explicit"
        )
    with pytest.raises(SelectionPlanError, match="operator"):
        compile_selection(
            ranges=[],
            order="input",
            branch="all",
            filters=[{"column": "A", "operator": "exec", "value": 1}],
        )


def test_unknown_branch_is_rejected_instead_of_guessed():
    with pytest.raises(SelectionPlanError, match="branch"):
        compile_selection(ranges=[], order="input", branch="turnaround")
