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
}
ALLOWED_OPTIONS = {
    "descriptive_statistics": set(),
    "linear_fit": set(),
    "polynomial_fit": {"degree", "polyorder"},
    "smooth": {"window", "polyorder"},
    "derivative": {"order", "derivative_method", "edge_order"},
    "peak_analysis": {"prominence", "distance", "height"},
    "nonlinear_fit": {"model", "initial_guess", "maxfev"},
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
    unknown = sorted(set(normalized_options) - ALLOWED_OPTIONS[method])
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
    opts = request.options

    if method == "descriptive_statistics":
        return {
            "count": int(y.size),
            "mean": float(np.mean(y)),
            "median": float(np.median(y)),
            "std": float(np.std(y, ddof=1)) if y.size > 1 else 0.0,
            "min": float(np.min(y)),
            "max": float(np.max(y)),
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
        params, covariance = curve_fit(model, x, y, p0=initial, maxfev=int(opts.get("maxfev", 10000)))
        fitted = model(x, *params)
        return {
            "model": model_name,
            "parameters": [float(value) for value in params],
            "fitted": [float(value) for value in fitted],
            "covariance": covariance.tolist(),
        }

    raise ValueError(f"Unsupported Origin analysis method: {method}")
