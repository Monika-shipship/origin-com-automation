"""Explicit analysis request validation and dispatch metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

SUPPORTED_ANALYSES = {
    "descriptive_statistics",
    "linear_fit",
    "polynomial_fit",
    "smooth",
    "derivative",
    "peak_analysis",
    "nonlinear_fit",
    "integration",
    "interpolation",
    "normalization",
    "fft",
    "correlation",
    "one_sample_ttest",
    "two_sample_ttest",
    "paired_ttest",
    "one_way_anova",
    "pca",
}
ALLOWED_OPTIONS = {
    "descriptive_statistics": set(),
    "linear_fit": set(),
    "polynomial_fit": {"degree", "polyorder"},
    "smooth": {"window", "polyorder"},
    "derivative": {"order", "derivative_method", "edge_order"},
    "peak_analysis": {"prominence", "distance", "height"},
    "nonlinear_fit": {
        "model",
        "initial_guess",
        "maxfev",
        "bounds",
        "parameter_names",
    },
    "integration": set(),
    "interpolation": {"interpolation_kind", "interpolation_points"},
    "normalization": {"normalization_method"},
    "fft": {"sample_spacing"},
    "correlation": {"correlation_method"},
    "one_sample_ttest": {"population_mean", "alternative"},
    "two_sample_ttest": {"equal_variance", "alternative"},
    "paired_ttest": {"alternative"},
    "one_way_anova": {"groups"},
    "pca": {"components", "standardize"},
}


@dataclass(frozen=True)
class AnalysisRequest:
    method: str
    x_column: str
    y_column: str
    options: dict[str, Any] = field(default_factory=dict)


def build_analysis_request(
    *,
    method: str,
    x_column: str,
    y_column: str,
    options: dict[str, Any] | None = None,
) -> AnalysisRequest:
    if method not in SUPPORTED_ANALYSES:
        raise ValueError(f"Unsupported Origin analysis method: {method}")
    if not x_column.strip() or not y_column.strip():
        raise ValueError("x_column and y_column are required")
    normalized_options = dict(options or {})
    common_options = {"backend", "create_operation", "recalculate_mode"}
    unknown = sorted(set(normalized_options) - (ALLOWED_OPTIONS[method] | common_options))
    if unknown:
        raise ValueError(f"Unsupported {method} options: {', '.join(unknown)}")
    return AnalysisRequest(
        method=method,
        x_column=x_column,
        y_column=y_column,
        options=normalized_options,
    )


def _numeric_arrays(x_values: list[Any], y_values: list[Any]) -> tuple[np.ndarray, np.ndarray]:
    if len(x_values) != len(y_values) or not x_values:
        raise ValueError("x and y must contain the same non-zero number of values")
    x = np.asarray([float(value) for value in x_values], dtype=float)
    y = np.asarray([float(value) for value in y_values], dtype=float)
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("x and y must contain only finite numeric values")
    return x, y


def run_analysis_data(
    method: str,
    x_values: list[Any],
    y_values: list[Any],
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a deterministic analysis on an explicitly selected x/y branch."""

    request = build_analysis_request(
        method=method,
        x_column="x",
        y_column="y",
        options=options,
    )
    x, y = _numeric_arrays(x_values, y_values)
    opts = {
        key: value
        for key, value in request.options.items()
        if key not in {"create_operation", "recalculate_mode"}
    }
    backend = str(opts.get("backend", "python"))
    if backend != "python":
        raise ValueError("run_analysis_data only executes the python backend")

    if method == "descriptive_statistics":
        return {
            "count": int(y.size),
            "mean": float(np.mean(y)),
            "median": float(np.median(y)),
            "std": float(np.std(y, ddof=1)) if y.size > 1 else 0.0,
            "min": float(np.min(y)),
            "max": float(np.max(y)),
        }

    if method == "integration":
        if x.size < 2:
            raise ValueError("integration requires at least two samples")
        return {
            "method": "trapezoid",
            "area": float(np.trapezoid(y, x)),
            "sample_count": int(x.size),
            "backend": backend,
        }

    if method == "interpolation":
        from scipy.interpolate import interp1d

        if x.size < 2 or np.any(np.diff(x) <= 0):
            raise ValueError("interpolation x values must be strictly increasing")
        kind = str(opts.get("interpolation_kind", "linear"))
        if kind not in {"linear", "nearest", "cubic"}:
            raise ValueError("interpolation_kind must be linear, nearest, or cubic")
        points = opts.get("interpolation_points")
        if not isinstance(points, list) or not points:
            raise ValueError("interpolation_points must be a non-empty list")
        requested = np.asarray([float(value) for value in points], dtype=float)
        if not np.isfinite(requested).all():
            raise ValueError("interpolation_points must be finite")
        if np.any(requested < x[0]) or np.any(requested > x[-1]):
            raise ValueError("interpolation_points must stay inside the selected x range")
        if kind == "cubic" and x.size < 4:
            raise ValueError("cubic interpolation requires at least four samples")
        interpolated = interp1d(x, y, kind=kind)(requested)
        return {
            "x": requested.tolist(),
            "interpolated": [float(value) for value in interpolated],
            "interpolation_kind": kind,
            "backend": backend,
        }

    if method == "normalization":
        normalization_method = str(opts.get("normalization_method", "min_max"))
        if normalization_method == "min_max":
            scale = float(np.max(y) - np.min(y))
            if scale == 0:
                raise ValueError("min_max normalization requires a non-constant y range")
            normalized = (y - np.min(y)) / scale
        elif normalization_method == "z_score":
            if y.size < 2:
                raise ValueError("z_score normalization requires at least two samples")
            scale = float(np.std(y, ddof=1))
            if scale == 0:
                raise ValueError("z_score normalization requires non-constant y values")
            normalized = (y - np.mean(y)) / scale
        elif normalization_method == "area":
            area = float(np.trapezoid(y, x))
            if area == 0:
                raise ValueError("area normalization requires a non-zero signed area")
            normalized = y / area
        else:
            raise ValueError("normalization_method must be min_max, z_score, or area")
        return {
            "x": x.tolist(),
            "normalized": [float(value) for value in normalized],
            "normalization_method": normalization_method,
            "backend": backend,
        }

    if method == "fft":
        sample_spacing = float(opts.get("sample_spacing", 1.0))
        if sample_spacing <= 0 or not np.isfinite(sample_spacing):
            raise ValueError("sample_spacing must be a positive finite number")
        spectrum = np.fft.fft(y)
        inverse = np.fft.ifft(spectrum)
        return {
            "frequency": np.fft.fftfreq(y.size, d=sample_spacing).tolist(),
            "spectrum_real": spectrum.real.tolist(),
            "spectrum_imag": spectrum.imag.tolist(),
            "magnitude": np.abs(spectrum).tolist(),
            "inverse": inverse.real.tolist(),
            "sample_spacing": sample_spacing,
            "backend": backend,
        }

    if method == "correlation":
        from scipy import stats

        if x.size < 3:
            raise ValueError("correlation requires at least three paired samples")
        correlation_method = str(opts.get("correlation_method", "pearson"))
        if correlation_method == "pearson":
            result = stats.pearsonr(x, y)
        elif correlation_method == "spearman":
            result = stats.spearmanr(x, y)
        else:
            raise ValueError("correlation_method must be pearson or spearman")
        return {
            "correlation_method": correlation_method,
            "coefficient": float(result.statistic),
            "p_value": float(result.pvalue),
            "sample_count": int(x.size),
            "backend": backend,
        }

    if method in {"one_sample_ttest", "two_sample_ttest", "paired_ttest"}:
        from scipy import stats

        alternative = str(opts.get("alternative", "two-sided"))
        if alternative not in {"two-sided", "less", "greater"}:
            raise ValueError("alternative must be two-sided, less, or greater")
        if method == "one_sample_ttest":
            population_mean = float(opts.get("population_mean", 0.0))
            result = stats.ttest_1samp(y, popmean=population_mean, alternative=alternative)
            extra = {"population_mean": population_mean, "paired": False}
        elif method == "two_sample_ttest":
            equal_variance = bool(opts.get("equal_variance", False))
            result = stats.ttest_ind(
                x,
                y,
                equal_var=equal_variance,
                alternative=alternative,
            )
            extra = {"equal_variance": equal_variance, "paired": False}
        else:
            result = stats.ttest_rel(x, y, alternative=alternative)
            extra = {"paired": True}
        return {
            "statistic": float(result.statistic),
            "p_value": float(result.pvalue),
            "alternative": alternative,
            "backend": backend,
            **extra,
        }

    if method == "one_way_anova":
        from scipy import stats

        raw_groups = opts.get("groups")
        if not isinstance(raw_groups, list) or len(raw_groups) < 2:
            raise ValueError("one_way_anova requires at least two explicit groups")
        groups: list[np.ndarray] = []
        for group in raw_groups:
            values = np.asarray(group, dtype=float)
            if values.size < 2 or not np.isfinite(values).all():
                raise ValueError("every ANOVA group must contain at least two finite values")
            groups.append(values)
        result = stats.f_oneway(*groups)
        return {
            "statistic": float(result.statistic),
            "p_value": float(result.pvalue),
            "group_count": len(groups),
            "group_sizes": [int(group.size) for group in groups],
            "backend": backend,
        }

    if method == "pca":
        matrix = np.column_stack((x, y))
        components = int(opts.get("components", 2))
        if components < 1 or components > min(matrix.shape):
            raise ValueError("components must be between 1 and the selected matrix rank")
        standardize = bool(opts.get("standardize", True))
        centered = matrix - np.mean(matrix, axis=0)
        if standardize:
            scale = np.std(centered, axis=0, ddof=1)
            if np.any(scale == 0):
                raise ValueError("PCA standardization requires non-constant columns")
            centered = centered / scale
        _, singular_values, vt = np.linalg.svd(centered, full_matrices=False)
        explained = singular_values**2 / max(matrix.shape[0] - 1, 1)
        total = float(np.sum(explained))
        ratios = explained / total if total else np.zeros_like(explained)
        selected_vectors = vt[:components]
        scores = centered @ selected_vectors.T
        return {
            "components": selected_vectors.tolist(),
            "scores": scores.tolist(),
            "explained_variance": explained[:components].tolist(),
            "explained_variance_ratio": ratios[:components].tolist(),
            "component_count": components,
            "standardize": standardize,
            "backend": backend,
        }

    if method in {"linear_fit", "polynomial_fit"}:
        degree = 1 if method == "linear_fit" else int(opts.get("degree", opts.get("polyorder", 2)))
        if degree < 1 or degree >= x.size:
            raise ValueError("fit degree must be at least 1 and smaller than the sample count")
        coefficients = np.polyfit(x, y, degree)
        fitted = np.polyval(coefficients, x)
        residual = y - fitted
        total = float(np.sum((y - np.mean(y)) ** 2))
        r_squared = 1.0 if total == 0 else 1.0 - float(np.sum(residual**2)) / total
        payload: dict[str, Any] = {
            "degree": degree,
            "coefficients": [float(value) for value in coefficients],
            "fitted": [float(value) for value in fitted],
            "r_squared": r_squared,
        }
        if degree == 1:
            payload["slope"] = float(coefficients[0])
            payload["intercept"] = float(coefficients[1])
        return payload

    if method == "smooth":
        from scipy.signal import savgol_filter

        window = int(opts.get("window", 5))
        if window < 3 or window % 2 == 0:
            raise ValueError("smoothing window must be an odd integer of at least 3")
        if window > y.size:
            raise ValueError("smoothing window must not exceed the sample count")
        polyorder = int(opts.get("polyorder", 2))
        if window <= polyorder:
            raise ValueError("smoothing window must be larger than polyorder")
        smoothed = savgol_filter(y, window_length=window, polyorder=polyorder)
        return {"x": x.tolist(), "smoothed": [float(value) for value in smoothed], "window": window}

    if method == "derivative":
        order = int(opts.get("order", 1))
        if order < 1:
            raise ValueError("derivative order must be at least 1")
        derivative_method = str(opts.get("derivative_method", "gradient")).lower()
        if derivative_method not in {"gradient", "forward", "backward", "central"}:
            raise ValueError(
                "derivative_method must be gradient, forward, backward, or central"
            )
        edge_order = int(opts.get("edge_order", 1))
        if edge_order not in {1, 2}:
            raise ValueError("edge_order must be 1 or 2")
        derivative_x = x.copy()
        derivative = y.copy()
        for _ in range(order):
            if np.any(np.diff(derivative_x) == 0):
                raise ValueError("x values must not repeat for derivative analysis")
            if derivative_method == "gradient":
                if derivative.size < edge_order + 1:
                    raise ValueError("Not enough points for the requested gradient edge_order")
                derivative = np.gradient(derivative, derivative_x, edge_order=edge_order)
            elif derivative_method in {"forward", "backward"}:
                if derivative.size < 2:
                    raise ValueError("Not enough points for the requested derivative order")
                derivative = np.diff(derivative) / np.diff(derivative_x)
                derivative_x = (
                    derivative_x[:-1]
                    if derivative_method == "forward"
                    else derivative_x[1:]
                )
            else:
                if derivative.size < 3:
                    raise ValueError("Not enough points for a central derivative")
                derivative = (derivative[2:] - derivative[:-2]) / (
                    derivative_x[2:] - derivative_x[:-2]
                )
                derivative_x = derivative_x[1:-1]
        return {
            "x": derivative_x.tolist(),
            "order": order,
            "derivative_method": derivative_method,
            "edge_order": edge_order if derivative_method == "gradient" else None,
            "derivative": [float(value) for value in derivative],
        }

    if method == "peak_analysis":
        from scipy.signal import find_peaks

        indices, properties = find_peaks(
            y,
            prominence=opts.get("prominence"),
            distance=opts.get("distance"),
            height=opts.get("height"),
        )
        return {
            "indices": [int(value) for value in indices],
            "x": [float(x[index]) for index in indices],
            "y": [float(y[index]) for index in indices],
            "properties": {
                key: [float(value) for value in values]
                for key, values in properties.items()
            },
            "backend": backend,
        }

    if method == "nonlinear_fit":
        from scipy.optimize import curve_fit

        model_name = str(opts.get("model", "exponential"))
        if model_name == "exponential":
            def model(values, a, b, c):
                return a * np.exp(b * values) + c

            default_guess = [float(np.max(y) - np.min(y) or 1.0), 0.0, float(np.min(y))]
        elif model_name == "gaussian":
            def model(values, amplitude, center, sigma, offset):
                return amplitude * np.exp(-((values - center) ** 2) / (2 * sigma**2)) + offset

            default_guess = [float(np.max(y) - np.min(y) or 1.0), float(x[np.argmax(y)]), 1.0, float(np.min(y))]
        else:
            raise ValueError("nonlinear model must be exponential or gaussian")
        initial = opts.get("initial_guess", default_guess)
        raw_bounds = opts.get("bounds", (-np.inf, np.inf))
        if (
            isinstance(raw_bounds, list)
            and len(raw_bounds) == 2
            and all(isinstance(item, list) for item in raw_bounds)
        ):
            bounds = (raw_bounds[0], raw_bounds[1])
        elif raw_bounds == (-np.inf, np.inf):
            bounds = raw_bounds
        else:
            raise ValueError("bounds must contain explicit lower and upper lists")
        params, covariance = curve_fit(
            model,
            x,
            y,
            p0=initial,
            bounds=bounds,
            maxfev=int(opts.get("maxfev", 10000)),
        )
        fitted = model(x, *params)
        parameter_names = opts.get("parameter_names")
        if parameter_names is None:
            parameter_names = (
                ["a", "b", "c"]
                if model_name == "exponential"
                else ["amplitude", "center", "sigma", "offset"]
            )
        if len(parameter_names) != len(params):
            raise ValueError("parameter_names must match the fitted parameter count")
        return {
            "model": model_name,
            "parameters": [float(value) for value in params],
            "named_parameters": {
                str(name): float(value)
                for name, value in zip(parameter_names, params, strict=True)
            },
            "fitted": [float(value) for value in fitted],
            "covariance": covariance.tolist(),
            "backend": backend,
        }

    raise ValueError(f"Unsupported Origin analysis method: {method}")
