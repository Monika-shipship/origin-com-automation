"""Version-aware planning for Origin-native formulas and analysis operations."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal


class NativeExpressionError(ValueError):
    code = "NATIVE_EXPRESSION_INVALID"


ExpressionStatus = Literal["verified", "supported_unverified", "unsupported"]
ExpressionRoute = Literal[
    "column_formula", "xfunction_operation", "python_explicit"
]


@dataclass(frozen=True)
class FormulaDiagnostic:
    code: str
    severity: Literal["warning", "error"]
    message: str
    suggestion: str | None = None
    applied: bool = False


@dataclass(frozen=True)
class NativeExpressionCapability:
    name: str
    route: Literal["column_formula", "xfunction_operation"]
    status: ExpressionStatus
    min_origin_major: int | None = None
    recalculating: bool = True
    notes: str | None = None


@dataclass(frozen=True)
class ExpressionPlan:
    executable: bool
    route: ExpressionRoute | None
    native_name: str | None
    status: ExpressionStatus
    expression: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    required_decision: dict[str, Any] | None = None
    diagnostics: tuple[FormulaDiagnostic, ...] = field(default_factory=tuple)


_CAPABILITIES: dict[str, NativeExpressionCapability] = {
    "abs": NativeExpressionCapability("abs", "column_formula", "verified"),
    "exp": NativeExpressionCapability("exp", "column_formula", "verified"),
    "ln": NativeExpressionCapability("ln", "column_formula", "verified"),
    "log10": NativeExpressionCapability("log10", "column_formula", "verified"),
    "sqrt": NativeExpressionCapability("sqrt", "column_formula", "verified"),
    "dderivative": NativeExpressionCapability(
        "dderivative",
        "column_formula",
        "supported_unverified",
        notes="Exact Set Column Values signature requires live version-specific proof.",
    ),
    "differentiate": NativeExpressionCapability(
        "differentiate",
        "xfunction_operation",
        "verified",
        min_origin_major=10,
        notes="Installed Origin 10.1 XFC exposes iy/order/smooth/poly/npts/oy/plot.",
    ),
}

_SAFE_ARGUMENT = re.compile(r"^[A-Za-z0-9_.$\[\]!():,+\-*/ ]+$")


def _origin_major(version: str | None) -> int | None:
    if not version:
        return None
    match = re.match(r"\s*(\d+)", version)
    return int(match.group(1)) if match else None


def _available(
    capability: NativeExpressionCapability, origin_version: str | None
) -> bool:
    major = _origin_major(origin_version)
    return (
        capability.min_origin_major is None
        or major is None
        or major >= capability.min_origin_major
    )


def validate_formula_expression(formula: str) -> tuple[FormulaDiagnostic, ...]:
    normalized = formula.strip()
    if not normalized:
        raise NativeExpressionError("formula must not be empty")
    if any(token in normalized for token in (";", "\r", "\n", "\x00")):
        raise NativeExpressionError("formula contains a script delimiter or control character")
    depth = 0
    for character in normalized:
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                raise NativeExpressionError("formula parentheses are unbalanced")
    if depth:
        raise NativeExpressionError("formula parentheses are unbalanced")

    diagnostics: list[FormulaDiagnostic] = []
    if re.search(r"\b(?:numpy|np)\.log\s*\(", normalized, re.IGNORECASE):
        diagnostics.append(
            FormulaDiagnostic(
                code="FUNCTION_COMPATIBILITY",
                severity="warning",
                message="NumPy log syntax is not an Origin column function",
                suggestion="Use the verified Origin function ln(...) if natural log is intended",
            )
        )
    if re.search(r"/\s*[+-]?0(?:\.0*)?(?![\d.])", normalized):
        diagnostics.append(
            FormulaDiagnostic(
                code="POSSIBLE_DIVISION_BY_ZERO",
                severity="warning",
                message="Formula contains division by a literal zero",
            )
        )
    if re.search(r"\b(?:ln|log|log10)\s*\(", normalized, re.IGNORECASE):
        diagnostics.append(
            FormulaDiagnostic(
                code="LOG_DOMAIN_REQUIRES_VALIDATION",
                severity="warning",
                message="Logarithm input must be positive over the selected rows",
            )
        )
    if re.search(r"\b(?:i|row)\s*[+\-*/]", normalized, re.IGNORECASE):
        diagnostics.append(
            FormulaDiagnostic(
                code="DYNAMIC_INDEX_REQUIRES_RANGE_CHECK",
                severity="warning",
                message="Dynamic row indexing requires an explicit boundary audit",
            )
        )
    return tuple(diagnostics)


def plan_native_expression(
    *,
    name: str,
    arguments: list[str | int | float],
    origin_version: str | None,
    allow_unverified: bool = False,
) -> ExpressionPlan:
    normalized_name = name.strip().lower()
    capability = _CAPABILITIES.get(normalized_name)
    if capability is None or not _available(capability, origin_version):
        return ExpressionPlan(False, None, normalized_name or None, "unsupported")
    rendered: list[str] = []
    for argument in arguments:
        text = str(argument).strip()
        if not text or not _SAFE_ARGUMENT.fullmatch(text):
            raise NativeExpressionError(f"unsafe native-function argument: {argument!r}")
        rendered.append(text)
    expression = f"{normalized_name}({','.join(rendered)})"
    diagnostics = validate_formula_expression(expression)
    if capability.status == "supported_unverified" and not allow_unverified:
        return ExpressionPlan(
            executable=False,
            route=None,
            native_name=normalized_name,
            status=capability.status,
            expression=expression,
            required_decision={
                "field": "allow_unverified_native_function",
                "message": f"{normalized_name} requires explicit version-specific approval",
            },
            diagnostics=diagnostics,
        )
    return ExpressionPlan(
        executable=True,
        route=capability.route,
        native_name=normalized_name,
        status=capability.status,
        expression=expression,
        diagnostics=diagnostics,
    )


def _combine_xy_range(x_range: str, y_range: str) -> str:
    pattern = re.compile(r"^(?P<prefix>\[[^\]]+\][^!]+)!(?P<column>[A-Za-z]+)$")
    x_match = pattern.fullmatch(x_range.strip())
    y_match = pattern.fullmatch(y_range.strip())
    if not x_match or not y_match or x_match.group("prefix") != y_match.group("prefix"):
        raise NativeExpressionError(
            "differentiate requires X and Y columns from the same stable worksheet ref"
        )
    return (
        f"{x_match.group('prefix')}!"
        f"({x_match.group('column')},{y_match.group('column')})"
    )


def plan_derivative_expression(
    *,
    method: str,
    order: int,
    x_range: str,
    y_range: str,
    backend_policy: Literal[
        "origin_native_only", "origin_native_preferred", "external_explicit"
    ],
    origin_version: str | None,
    smooth: bool = False,
    polyorder: int | None = None,
    points: int | None = None,
    allow_unverified: bool = False,
) -> ExpressionPlan:
    if isinstance(order, bool) or order < 1:
        raise NativeExpressionError("derivative order must be a positive integer")
    normalized = method.strip().lower()
    if backend_policy == "external_explicit":
        return ExpressionPlan(
            executable=True,
            route="python_explicit",
            native_name=None,
            status="verified",
            parameters={"method": normalized, "order": order},
        )
    if normalized == "dderivative":
        return plan_native_expression(
            name="dderivative",
            arguments=[y_range, x_range, order],
            origin_version=origin_version,
            allow_unverified=allow_unverified,
        )
    if normalized == "differentiate":
        capability = _CAPABILITIES["differentiate"]
        if not _available(capability, origin_version):
            return ExpressionPlan(False, None, "differentiate", "unsupported")
        parameters: dict[str, Any] = {
            "iy": _combine_xy_range(x_range, y_range),
            "order": order,
            "smooth": int(smooth),
            "plot": 0,
        }
        if smooth:
            if polyorder is None or points is None:
                return ExpressionPlan(
                    False,
                    None,
                    "differentiate",
                    capability.status,
                    required_decision={
                        "field": "smoothing_parameters",
                        "message": "Smoothed differentiation requires polyorder and points",
                    },
                )
            parameters.update({"poly": polyorder, "npts": points})
        return ExpressionPlan(
            executable=True,
            route="xfunction_operation",
            native_name="differentiate",
            status=capability.status,
            parameters=parameters,
        )
    return ExpressionPlan(
        executable=False,
        route=None,
        native_name=None,
        status="unsupported",
        required_decision={
            "field": "backend_or_native_method",
            "message": (
                f"Derivative method {normalized!r} has no verified equivalent native route; "
                "choose an exact native method or explicitly approve the external backend"
            ),
        },
    )
