"""Execution and tracking of plugin-created native Analysis Operations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Mapping

from .common import NativeValidationError, RangeRef
from .xfunctions import XFunctionPlan


_OPERATION_REF = re.compile(r"^op://([a-z][a-z0-9_]*)/([a-f0-9]{6,64})$")
_TEMPLATE_EXTENSIONS = {".ogwu", ".otwu"}
_COLUMN_WITH_LABEL = re.compile(r'^(?P<column>[A-Za-z]+|\d+)"[^"]*"$')
_LABELED_COLUMN_RANGE = re.compile(
    r"^(?P<prefix>\[[^\]]+\][^!]+!\()(?P<body>[^()]*)\)$"
)


def normalize_operation_ref(value: str) -> str:
    normalized = value.strip().lower()
    if not _OPERATION_REF.fullmatch(normalized):
        raise NativeValidationError(f"invalid operation ref: {value!r}")
    return normalized


class AnalysisOperationRegistry:
    """Thread-safe metadata for operations created by this controller."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._operations: dict[str, dict[str, Any]] = {}

    def register(
        self,
        *,
        operation_ref: str,
        xfunction: str,
        operation_range: str,
        recalculate_mode: str,
        result_refs: Mapping[str, str],
    ) -> dict[str, Any]:
        normalized_ref = normalize_operation_ref(operation_ref)
        safe_range = RangeRef(operation_range).value
        record = {
            "operation_ref": normalized_ref,
            "xfunction": xfunction,
            "operation_range": safe_range,
            "recalculate_mode": recalculate_mode,
            "result_refs": dict(result_refs),
            "managed_by_plugin": True,
            "status": "registered",
        }
        with self._lock:
            self._operations[normalized_ref] = record
        return dict(record)

    def get(self, operation_ref: str) -> dict[str, Any]:
        normalized_ref = normalize_operation_ref(operation_ref)
        with self._lock:
            try:
                return dict(self._operations[normalized_ref])
            except KeyError as exc:
                raise NativeValidationError(
                    f"operation ref is not managed by this plugin: {normalized_ref}",
                    code="ANALYSIS_OPERATION_NOT_FOUND",
                ) from exc

    def update(self, operation_ref: str, **changes: Any) -> dict[str, Any]:
        normalized_ref = normalize_operation_ref(operation_ref)
        with self._lock:
            if normalized_ref not in self._operations:
                raise NativeValidationError(
                    f"operation ref is not managed by this plugin: {normalized_ref}",
                    code="ANALYSIS_OPERATION_NOT_FOUND",
                )
            self._operations[normalized_ref].update(changes)
            return dict(self._operations[normalized_ref])

    def list(self, scope_ref: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            records = [dict(item) for item in self._operations.values()]
        if scope_ref is None:
            return records
        safe_scope = RangeRef(scope_ref).value.casefold()
        return [
            item
            for item in records
            if item["operation_range"].casefold().startswith(safe_scope)
        ]


def _execute(app: Any, command: str, *, action: str) -> None:
    result = app.Execute(command)
    if result is False or result == 0:
        raise NativeValidationError(
            f"Origin did not confirm {action}", code="NATIVE_EXECUTION_FAILED"
        )


def normalize_xfunction_output_range(value: str) -> str:
    """Remove Origin column long-name annotations from an X-Function range."""

    normalized = value.strip()
    match = _LABELED_COLUMN_RANGE.fullmatch(normalized)
    if match:
        columns = []
        for raw_column in match.group("body").split(","):
            token = raw_column.strip()
            labeled = _COLUMN_WITH_LABEL.fullmatch(token)
            if labeled:
                token = labeled.group("column")
            if not re.fullmatch(r"[A-Za-z]+|\d+", token):
                raise NativeValidationError(
                    f"Origin returned an unsupported output range: {value!r}",
                    code="XFUNCTION_OUTPUT_UNCONFIRMED",
                )
            columns.append(token)
        if not columns:
            raise NativeValidationError(
                "Origin returned an empty X-Function output range",
                code="XFUNCTION_OUTPUT_UNCONFIRMED",
            )
        normalized = f'{match.group("prefix")}{",".join(columns)})'
    else:
        head, quote, _label = normalized.partition('"')
        if quote:
            normalized = head
    try:
        return RangeRef(normalized).value
    except NativeValidationError as exc:
        raise NativeValidationError(
            f"Origin returned an invalid output range: {value!r}",
            code="XFUNCTION_OUTPUT_UNCONFIRMED",
        ) from exc


def _resolved_outputs(app: Any, plan: XFunctionPlan) -> dict[str, str]:
    outputs = {key: value.value for key, value in plan.outputs.items()}
    dynamic_keys = [key for key, value in outputs.items() if value == "<new>"]
    if plan.create_operation and not outputs and plan.operation_output:
        dynamic_keys.append(plan.operation_output)
    for key in dynamic_keys:
        raw_range = str(app.LTStr(f"{plan.name}.{key}$") or "").strip()
        if not raw_range:
            raise NativeValidationError(
                f"Origin did not report the {plan.name}.{key} output range",
                code="XFUNCTION_OUTPUT_UNCONFIRMED",
            )
        outputs[key] = normalize_xfunction_output_range(raw_range)
    return outputs


def execute_xfunction_plan(
    app: Any,
    plan: XFunctionPlan,
    registry: AnalysisOperationRegistry,
) -> dict[str, Any]:
    _execute(app, plan.command, action=f"X-Function {plan.name}")
    resolved_outputs = _resolved_outputs(app, plan)
    data: dict[str, Any] = {
        "xfunction": plan.name,
        "verified": plan.verified,
        "parameters": dict(plan.redacted_parameters),
        "outputs": resolved_outputs,
        "operation_created": plan.create_operation,
        "native_operation_created": plan.create_operation,
        "editable_in_origin": plan.create_operation,
        "operation_ref": plan.operation_ref,
        "recalculate_mode": plan.recalculate_mode,
    }
    if plan.create_operation:
        operation_range = next(iter(resolved_outputs.values()), plan.operation_range)
        if not plan.operation_ref or not operation_range:
            raise NativeValidationError(
                "operation creation requires an explicit input or output range"
            )
        registry.register(
            operation_ref=plan.operation_ref,
            xfunction=plan.name,
            operation_range=operation_range,
            recalculate_mode=plan.recalculate_mode,
            result_refs=resolved_outputs,
        )
    return data


def build_get_operation_command(operation_range: str) -> str:
    safe_range = RangeRef(operation_range).value
    return f"op_change ir:={safe_range} tr:=__codex_op_tree op:=get;"


def build_recalculate_operation_command(operation_range: str) -> str:
    safe_range = RangeRef(operation_range).value
    return f"op_change ir:={safe_range} tr:=__codex_op_tree op:=run;"


def read_analysis_operation(
    app: Any,
    operation_ref: str,
    registry: AnalysisOperationRegistry,
) -> dict[str, Any]:
    record = registry.get(operation_ref)
    _execute(
        app,
        build_get_operation_command(record["operation_range"]),
        action="Analysis Operation readback",
    )
    return registry.update(
        operation_ref,
        status="available",
        native_query_confirmed=True,
    )


def recalculate_operation(
    app: Any,
    operation_ref: str,
    registry: AnalysisOperationRegistry,
    *,
    wait: bool = True,
) -> dict[str, Any]:
    record = registry.get(operation_ref)
    _execute(
        app,
        build_recalculate_operation_command(record["operation_range"]),
        action="Analysis Operation recalculation",
    )
    if not wait:
        return registry.update(operation_ref, status="pending", recalculated=False)
    verified = read_analysis_operation(app, operation_ref, registry)
    if verified["status"] != "available":
        raise NativeValidationError(
            "Analysis Operation recalculation could not be confirmed",
            code="ANALYSIS_RECALCULATION_UNCONFIRMED",
        )
    return registry.update(operation_ref, recalculated=True)


@dataclass(frozen=True)
class AnalysisTemplatePlan:
    action: str
    path: Path
    workbook_ref: str | None
    overwrite: bool
    command: str


def build_analysis_template_plan(
    *,
    action: str,
    path: str,
    workbook_ref: str | None = None,
    overwrite: bool = False,
) -> AnalysisTemplatePlan:
    normalized_action = action.strip().lower()
    if normalized_action not in {"save", "load"}:
        raise NativeValidationError("analysis template action must be save or load")
    target = Path(path).expanduser().resolve()
    if target.suffix.lower() not in _TEMPLATE_EXTENSIONS:
        raise NativeValidationError("analysis template extension must be .ogwu or .otwu")
    if normalized_action == "save":
        if workbook_ref is None:
            raise NativeValidationError("saving an analysis template requires workbook_ref")
        RangeRef(workbook_ref)
        if target.exists() and not overwrite:
            raise NativeValidationError(f"analysis template already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        command = f'save -ik "{target.as_posix()}";'
    else:
        if not target.is_file():
            raise NativeValidationError(f"analysis template does not exist: {target}")
        command = f'doc -a "{target.as_posix()}";'
    return AnalysisTemplatePlan(
        action=normalized_action,
        path=target,
        workbook_ref=workbook_ref,
        overwrite=overwrite,
        command=command,
    )


def execute_analysis_template_plan(app: Any, plan: AnalysisTemplatePlan) -> dict[str, Any]:
    _execute(app, plan.command, action=f"analysis template {plan.action}")
    if plan.action == "save":
        if not plan.path.is_file() or plan.path.stat().st_size == 0:
            raise NativeValidationError(
                f"analysis template was not created: {plan.path}",
                code="ANALYSIS_TEMPLATE_UNCONFIRMED",
            )
    return {
        "action": plan.action,
        "path": str(plan.path),
        "workbook_ref": plan.workbook_ref,
        "verified": True,
    }
