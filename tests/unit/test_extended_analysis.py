import numpy as np
import pytest

from origin_com_automation.services.analysis import run_analysis_data


def test_trapezoidal_integration_reports_signed_area():
    result = run_analysis_data("integration", [0, 1, 2], [0, 1, 4], {})
    assert result["area"] == pytest.approx(3.0)
    assert result["method"] == "trapezoid"


def test_interpolation_uses_explicit_points_and_kind():
    result = run_analysis_data(
        "interpolation",
        [0, 1, 2],
        [0, 2, 4],
        {"interpolation_kind": "linear", "interpolation_points": [0.5, 1.5]},
    )
    assert result["x"] == [0.5, 1.5]
    assert result["interpolated"] == pytest.approx([1.0, 3.0])


@pytest.mark.parametrize(
    ("normalization_method", "expected"),
    [
        ("min_max", [0.0, 0.5, 1.0]),
        ("z_score", [-1.0, 0.0, 1.0]),
        ("area", [0.25, 0.5, 0.75]),
    ],
)
def test_normalization_methods_are_explicit(normalization_method, expected):
    result = run_analysis_data(
        "normalization",
        [0, 1, 2],
        [1, 2, 3],
        {"normalization_method": normalization_method},
    )
    assert result["normalized"] == pytest.approx(expected)
    assert result["normalization_method"] == normalization_method


def test_fft_reports_frequency_spectrum_and_round_trip():
    x = np.arange(8, dtype=float).tolist()
    y = np.sin(2 * np.pi * np.arange(8) / 8).tolist()
    result = run_analysis_data("fft", x, y, {"sample_spacing": 1.0})

    assert len(result["frequency"]) == 8
    assert result["inverse"] == pytest.approx(y, abs=1e-12)
    assert result["spectrum_real"][1] == pytest.approx(0.0, abs=1e-12)
    assert abs(result["spectrum_imag"][1]) == pytest.approx(4.0)


@pytest.mark.parametrize("correlation_method", ["pearson", "spearman"])
def test_correlation_reports_coefficient_and_p_value(correlation_method):
    result = run_analysis_data(
        "correlation",
        [1, 2, 3, 4],
        [2, 4, 6, 8],
        {"correlation_method": correlation_method},
    )
    assert result["coefficient"] == pytest.approx(1.0)
    assert result["p_value"] <= 0.01


def test_t_tests_keep_requested_alternative_and_pairing():
    one = run_analysis_data(
        "one_sample_ttest",
        [0, 1, 2, 3],
        [2, 3, 4, 5],
        {"population_mean": 0, "alternative": "greater"},
    )
    two = run_analysis_data(
        "two_sample_ttest",
        [1, 2, 3, 4],
        [3, 4, 5, 6],
        {"equal_variance": False, "alternative": "two-sided"},
    )
    paired = run_analysis_data(
        "paired_ttest",
        [1, 2, 4, 7],
        [2, 4, 5, 9],
        {"alternative": "less"},
    )
    assert one["alternative"] == "greater"
    assert two["equal_variance"] is False
    assert paired["paired"] is True
    assert paired["statistic"] < 0


def test_one_way_anova_uses_explicit_groups():
    result = run_analysis_data(
        "one_way_anova",
        [0, 1],
        [0, 1],
        {"groups": [[1, 2, 3], [4, 5, 6], [7, 8, 9]]},
    )
    assert result["group_count"] == 3
    assert result["statistic"] > 0


def test_pca_reports_explained_variance_for_explicit_component_count():
    result = run_analysis_data(
        "pca",
        [1, 2, 3, 4],
        [2, 4, 6, 8],
        {"components": 1, "standardize": True},
    )
    assert len(result["scores"][0]) == 1
    assert result["explained_variance_ratio"][0] == pytest.approx(1.0)


def test_nonlinear_fit_accepts_bounds_and_named_parameters():
    x = np.linspace(-2, 2, 41)
    y = 3 * np.exp(-((x - 0.4) ** 2) / (2 * 0.7**2)) + 0.2
    result = run_analysis_data(
        "nonlinear_fit",
        x.tolist(),
        y.tolist(),
        {
            "model": "gaussian",
            "initial_guess": [2.5, 0.0, 1.0, 0.0],
            "bounds": [[0, -2, 0.01, -1], [10, 2, 4, 2]],
            "parameter_names": ["amplitude", "center", "sigma", "offset"],
        },
    )
    assert result["named_parameters"]["center"] == pytest.approx(0.4, abs=1e-3)
    assert result["named_parameters"]["sigma"] == pytest.approx(0.7, abs=1e-3)


def test_analysis_rejects_unknown_options_instead_of_ignoring_them():
    with pytest.raises(ValueError, match="Unsupported fft options"):
        run_analysis_data("fft", [0, 1], [1, 2], {"window_typo": "hann"})


def test_peak_analysis_records_backend_without_changing_algorithm():
    result = run_analysis_data(
        "peak_analysis",
        [0, 1, 2],
        [0, 3, 0],
        {"backend": "python", "prominence": 1},
    )
    assert result["backend"] == "python"
    assert result["indices"] == [1]
