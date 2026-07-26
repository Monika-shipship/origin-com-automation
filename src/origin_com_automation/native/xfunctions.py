"""Structured allowlisted X-Function command planning."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from .common import (
    FileRef,
    NativeValidationError,
    OutputRef,
    RangeRef,
    labtalk_literal,
    validate_identifier,
)


@dataclass(frozen=True)
class ParameterRule:
    value_types: tuple[type, ...]
    required: bool = False


@dataclass(frozen=True)
class XFunctionSpec:
    parameters: Mapping[str, ParameterRule]
    outputs: frozenset[str]
    operation_output: str | None = None


RANGE = (RangeRef,)
SCALAR = (bool, int, float, str)

VERIFIED_XFUNCTIONS: dict[str, XFunctionSpec] = {
    "fitlr": XFunctionSpec(
        parameters={"iy": ParameterRule(RANGE, required=True)},
        outputs=frozenset({"oy", "report"}),
        operation_output="oy",
    ),
    "smooth": XFunctionSpec(
        parameters={
            "iy": ParameterRule(RANGE, required=True),
            "method": ParameterRule(SCALAR),
            "npts": ParameterRule((int,)),
            "polyorder": ParameterRule((int,)),
        },
        outputs=frozenset({"oy"}),
        operation_output="oy",
    ),
    "differentiate": XFunctionSpec(
        parameters={
            "iy": ParameterRule(RANGE, required=True),
            "order": ParameterRule((int,)),
        },
        outputs=frozenset({"oy"}),
        operation_output="oy",
    ),
    "fft1": XFunctionSpec(
        parameters={"ix": ParameterRule(RANGE), "iy": ParameterRule(RANGE, required=True)},
        outputs=frozenset({"ox", "oy", "report"}),
        operation_output="oy",
    ),
    "nlfit": XFunctionSpec(
        parameters={
            "iy": ParameterRule(RANGE, required=True),
            "func": ParameterRule((str,), required=True),
        },
        outputs=frozenset({"oy", "report"}),
        operation_output="oy",
    ),
    "peaks": XFunctionSpec(
        parameters={"iy": ParameterRule(RANGE, required=True)},
        outputs=frozenset({"oy", "report"}),
        operation_output="oy",
    ),
}

NATIVE_ANALYSIS_XFUNCTIONS = {
    "linear_fit": "fitlr",
    "fft": "fft1",
}

RECALCULATION_MODES = {"none": 0, "auto": 1, "manual": 2}


def verified_native_analysis_methods() -> list[str]:
    return sorted(NATIVE_ANALYSIS_XFUNCTIONS)


@dataclass(frozen=True)
class XFunctionPlan:
    name: str
    parameters: Mapping[str, Any]
    outputs: Mapping[str, OutputRef]
    command: str
    verified: bool
    create_operation: bool
    recalculate_mode: str
    operation_ref: str | None
    operation_range: str | None
    operation_output: str | None
    redacted_parameters: Mapping[str, Any]


def _display_value(value: Any) -> Any:
    if isinstance(value, (RangeRef, OutputRef, FileRef)):
        return value.value
    if isinstance(value, (list, tuple)):
        return [_display_value(item) for item in value]
    return value


def build_xfunction_plan(
    name: str,
    parameters: Mapping[str, Any],
    *,
    outputs: Mapping[str, OutputRef] | None = None,
    create_operation: bool = False,
    recalculate_mode: str = "none",
    allow_unverified: bool = False,
) -> XFunctionPlan:
    normalized_name = validate_identifier(name, kind="X-Function name")
    if recalculate_mode not in RECALCULATION_MODES:
        raise NativeValidationError(f"invalid recalculation mode: {recalculate_mode}")
    spec = VERIFIED_XFUNCTIONS.get(normalized_name)
    if spec is None and not allow_unverified:
        raise NativeValidationError(
            f"X-Function {normalized_name!r} is not verified; set allow_unverified explicitly",
            code="XFUNCTION_UNVERIFIED",
        )

    normalized_parameters = dict(parameters)
    normalized_outputs = dict(outputs or {})
    if spec is not None:
        unknown = sorted(set(normalized_parameters) - set(spec.parameters))
        if unknown:
            raise NativeValidationError(f"unknown parameter for {normalized_name}: {unknown[0]}")
        missing = sorted(
            key
            for key, rule in spec.parameters.items()
            if rule.required and key not in normalized_parameters
        )
        if missing:
            raise NativeValidationError(f"missing required parameter for {normalized_name}: {missing[0]}")
        for key, value in normalized_parameters.items():
            rule = spec.parameters[key]
            if not isinstance(value, rule.value_types) or (
                isinstance(value, bool) and bool not in rule.value_types
            ):
                expected = ", ".join(item.__name__ for item in rule.value_types)
                raise NativeValidationError(f"parameter {key!r} must be {expected}")
        unknown_outputs = sorted(set(normalized_outputs) - set(spec.outputs))
        if unknown_outputs:
            raise NativeValidationError(
                f"unknown output for {normalized_name}: {unknown_outputs[0]}"
            )

    for key in normalized_parameters:
        validate_identifier(key, kind="parameter name")
    for key, value in normalized_outputs.items():
        validate_identifier(key, kind="output name")
        if not isinstance(value, OutputRef):
            raise NativeValidationError(f"output {key!r} must use OutputRef")

    tokens = [normalized_name]
    if create_operation:
        tokens.extend(("-r", str(RECALCULATION_MODES[recalculate_mode])))
    tokens.extend(
        f"{key}:={labtalk_literal(value)}" for key, value in normalized_parameters.items()
    )
    tokens.extend(f"{key}:={labtalk_literal(value)}" for key, value in normalized_outputs.items())
    command = " ".join(tokens) + ";"

    operation_range = next((item.value for item in normalized_outputs.values()), None)
    if create_operation and operation_range is None:
        operation_range = next(
            (item.value for item in normalized_parameters.values() if isinstance(item, RangeRef)),
            None,
        )
    operation_ref = None
    if create_operation:
        digest_payload = {
            "name": normalized_name,
            "parameters": {key: _display_value(value) for key, value in normalized_parameters.items()},
            "outputs": {key: value.value for key, value in normalized_outputs.items()},
            "recalculate_mode": recalculate_mode,
        }
        digest = hashlib.sha256(
            json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:16]
        operation_ref = f"op://{normalized_name}/{digest}"

    return XFunctionPlan(
        name=normalized_name,
        parameters=normalized_parameters,
        outputs=normalized_outputs,
        command=command,
        verified=spec is not None,
        create_operation=create_operation,
        recalculate_mode=recalculate_mode,
        operation_ref=operation_ref,
        operation_range=operation_range,
        operation_output=spec.operation_output if spec is not None else None,
        redacted_parameters={
            key: _display_value(value) for key, value in normalized_parameters.items()
        },
    )
