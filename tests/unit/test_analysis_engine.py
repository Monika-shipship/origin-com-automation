import pytest

from origin_com_automation.services.analysis import run_analysis_data


def test_linear_fit_reports_slope_intercept_and_r_squared():
    result = run_analysis_data("linear_fit", [0, 1, 2], [1, 3, 5], {})

    assert result["slope"] == pytest.approx(2.0)
    assert result["intercept"] == pytest.approx(1.0)
    assert result["r_squared"] == pytest.approx(1.0)


def test_derivative_preserves_explicit_input_order():
    result = run_analysis_data("derivative", [0, 1, 2], [0, 1, 4], {})

    assert result["x"] == [0.0, 1.0, 2.0]
    assert result["derivative"] == pytest.approx([1.0, 2.0, 3.0])


def test_derivative_honors_requested_order():
    result = run_analysis_data(
        "derivative",
        [0, 1, 2, 3],
        [0, 1, 4, 9],
        {"order": 2},
    )

    assert result["order"] == 2
    assert result["derivative"] == pytest.approx([1.0, 1.5, 1.5, 1.0])


def test_derivative_honors_explicit_forward_and_central_methods():
    forward = run_analysis_data(
        "derivative",
        [0, 1, 2, 3],
        [0, 1, 4, 9],
        {"derivative_method": "forward"},
    )
    central = run_analysis_data(
        "derivative",
        [0, 1, 2, 3],
        [0, 1, 4, 9],
        {"derivative_method": "central"},
    )

    assert forward["x"] == [0.0, 1.0, 2.0]
    assert forward["derivative"] == pytest.approx([1.0, 3.0, 5.0])
    assert central["x"] == [1.0, 2.0]
    assert central["derivative"] == pytest.approx([2.0, 4.0])


def test_analysis_rejects_options_for_the_wrong_method():
    with pytest.raises(ValueError, match="Unsupported linear_fit options"):
        run_analysis_data("linear_fit", [0, 1], [0, 1], {"degree": 2})


def test_smoothing_never_changes_requested_window_silently():
    with pytest.raises(ValueError, match="odd"):
        run_analysis_data("smooth", [0, 1, 2, 3], [0, 1, 4, 9], {"window": 4})
    with pytest.raises(ValueError, match="sample count"):
        run_analysis_data("smooth", [0, 1, 2], [0, 1, 4], {"window": 5})
