import pytest

from origin_com_automation.native.expressions import (
    NativeExpressionError,
    plan_derivative_expression,
    plan_native_expression,
    validate_formula_expression,
)


def test_verified_column_function_is_preserved_instead_of_expanded_arithmetic():
    plan = plan_native_expression(
        name="sqrt",
        arguments=["col(A)"],
        origin_version="10.1.0.178",
    )

    assert plan.executable is True
    assert plan.route == "column_formula"
    assert plan.expression == "sqrt(col(A))"
    assert plan.native_name == "sqrt"
    assert plan.status == "verified"


def test_dderivative_requires_verified_or_explicit_unverified_route():
    blocked = plan_derivative_expression(
        method="dderivative",
        order=1,
        x_range="col(A)",
        y_range="col(B)",
        backend_policy="origin_native_preferred",
        origin_version="10.1.0.178",
    )

    assert blocked.executable is False
    assert blocked.status == "supported_unverified"
    assert blocked.required_decision["field"] == "allow_unverified_native_function"

    allowed = plan_derivative_expression(
        method="dderivative",
        order=1,
        x_range="col(A)",
        y_range="col(B)",
        backend_policy="origin_native_preferred",
        origin_version="10.1.0.178",
        allow_unverified=True,
    )
    assert allowed.route == "column_formula"
    assert allowed.expression == "dderivative(col(B),col(A),1)"


def test_differentiate_selects_native_analysis_operation_with_exact_parameters():
    plan = plan_derivative_expression(
        method="differentiate",
        order=2,
        x_range="[Book1]Data!A",
        y_range="[Book1]Data!B",
        backend_policy="origin_native_only",
        origin_version="10.1.0.178",
        smooth=False,
    )

    assert plan.executable is True
    assert plan.route == "xfunction_operation"
    assert plan.native_name == "differentiate"
    assert plan.parameters == {
        "iy": "[Book1]Data!(A,B)",
        "order": 2,
        "smooth": 0,
        "plot": 0,
    }


def test_unmapped_derivative_never_silently_selects_python():
    plan = plan_derivative_expression(
        method="central",
        order=1,
        x_range="col(A)",
        y_range="col(B)",
        backend_policy="origin_native_preferred",
        origin_version="10.1.0.178",
    )

    assert plan.executable is False
    assert plan.route is None
    assert plan.required_decision["field"] == "backend_or_native_method"

    external = plan_derivative_expression(
        method="central",
        order=1,
        x_range="col(A)",
        y_range="col(B)",
        backend_policy="external_explicit",
        origin_version="10.1.0.178",
    )
    assert external.route == "python_explicit"
    assert external.status == "verified"


def test_formula_diagnostics_are_advisory_and_do_not_rewrite():
    diagnostics = validate_formula_expression("numpy.log(col(A)) / 0")

    assert {item.code for item in diagnostics} >= {
        "FUNCTION_COMPATIBILITY",
        "POSSIBLE_DIVISION_BY_ZERO",
    }
    compatibility = next(item for item in diagnostics if item.code == "FUNCTION_COMPATIBILITY")
    assert compatibility.suggestion == "Use the verified Origin function ln(...) if natural log is intended"
    assert compatibility.applied is False


@pytest.mark.parametrize("formula", ["col(A); del -all", "sqrt((col(A))"])
def test_formula_validator_rejects_unsafe_or_unbalanced_expression(formula):
    with pytest.raises(NativeExpressionError):
        validate_formula_expression(formula)
