"""Shared errors and stable reference checks for Origin object plans."""

from __future__ import annotations

from ..native.common import NativeValidationError, RangeRef


class ObjectPlanError(ValueError):
    code = "OBJECT_PLAN_INVALID"


def stable_ref(value: str, *, kind: str) -> str:
    try:
        return RangeRef(value).value
    except NativeValidationError as exc:
        raise ObjectPlanError(f"unsafe {kind}: {value!r}") from exc


def reject_unknown(options: dict, allowed: set[str], *, action: str) -> None:
    unknown = sorted(set(options) - allowed)
    if unknown:
        raise ObjectPlanError(f"unknown options for {action}: {', '.join(unknown)}")

