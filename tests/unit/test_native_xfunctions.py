from pathlib import Path

import pytest

from origin_com_automation.native.common import (
    FileRef,
    NativeValidationError,
    OutputRef,
    RangeRef,
    labtalk_literal,
)
from origin_com_automation.native.xfunctions import build_xfunction_plan


def test_labtalk_literal_normalizes_and_quotes_paths():
    assert labtalk_literal(FileRef(r"C:\a b\x.csv")) == '"C:/a b/x.csv"'
    assert labtalk_literal(Path(r"C:\a b\x.csv")) == '"C:/a b/x.csv"'


def test_labtalk_literal_rejects_unsafe_string_tokens():
    with pytest.raises(NativeValidationError, match="unsafe"):
        labtalk_literal('x"; del -all')


def test_range_and_output_refs_reject_command_separators():
    for ref_type in (RangeRef, OutputRef):
        with pytest.raises(NativeValidationError, match="unsafe"):
            ref_type("[Book]1!A:B; run.section()")


def test_verified_xfunction_rejects_unknown_parameter():
    with pytest.raises(NativeValidationError, match="unknown parameter"):
        build_xfunction_plan(
            "fitlr",
            {"ix": RangeRef("[Book]1!A:B"), "typo": 1},
        )


def test_verified_xfunction_requires_typed_range_and_builds_exact_command():
    plan = build_xfunction_plan(
        "fitlr",
        {"ix": RangeRef("[Book1]Data!A:B")},
        outputs={"oy": OutputRef("[Book1]Fit!A:B")},
        create_operation=True,
        recalculate_mode="auto",
    )

    assert plan.name == "fitlr"
    assert plan.verified is True
    assert plan.command == (
        "fitlr ix:=[Book1]Data!A:B oy:=[Book1]Fit!A:B "
        "recalculate:=1;"
    )
    assert plan.operation_ref.startswith("op://fitlr/")
    assert plan.redacted_parameters == {"ix": "[Book1]Data!A:B"}


def test_unverified_xfunction_needs_explicit_opt_in():
    with pytest.raises(NativeValidationError, match="not verified"):
        build_xfunction_plan("customxf", {"n": 3})

    plan = build_xfunction_plan(
        "customxf",
        {"n": 3, "label": "safe label"},
        allow_unverified=True,
    )
    assert plan.verified is False
    assert plan.command == 'customxf n:=3 label:="safe label";'


@pytest.mark.parametrize("mode", ["none", "auto", "manual"])
def test_xfunction_recalculation_modes_are_explicit(mode):
    plan = build_xfunction_plan(
        "smooth",
        {"iy": RangeRef("[Book]1!B")},
        create_operation=True,
        recalculate_mode=mode,
    )
    expected = {"none": 0, "auto": 1, "manual": 2}[mode]
    assert f"recalculate:={expected}" in plan.command
