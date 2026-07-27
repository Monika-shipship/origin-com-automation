"""Bounded, target-specific verification for workflow deliverables."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from ..contracts import ResultEnvelope


AuditKind = Literal[
    "worksheet", "connector", "formula", "operation", "graph", "file", "shutdown"
]


@dataclass(frozen=True)
class AuditTarget:
    kind: AuditKind
    ref: str
    expected: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.ref.strip() or self.ref.strip() in {"*", "all", "project:*"}:
            raise ValueError("audit targets must be bounded stable references")


def _subset_mismatches(expected: Any, actual: Any, prefix: str = "") -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [{"field": prefix or "value", "expected": expected, "actual": actual}]
        for key, value in expected.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            if key not in actual:
                mismatches.append({"field": child, "expected": value, "actual": None})
            else:
                mismatches.extend(_subset_mismatches(value, actual[key], child))
    elif expected != actual:
        mismatches.append({"field": prefix or "value", "expected": expected, "actual": actual})
    return mismatches


def _worksheet_check(controller: Any, target: AuditTarget) -> ResultEnvelope:
    result = controller.read_worksheet(target.ref, data_format="variant")
    if not result.success:
        return result
    data = result.data or {}
    values = data.get("values", [])
    minimum = int(target.expected.get("minimum_rows", 0))
    mismatches: list[dict[str, Any]] = []
    if len(values) < minimum:
        mismatches.append({"field": "rows", "expected": f">={minimum}", "actual": len(values)})
    for coordinate, expected in target.expected.get("representative_values", {}).items():
        try:
            row, column = (int(value) for value in coordinate.split(",", 1))
            actual = values[row][column]
        except (IndexError, TypeError, ValueError):
            actual = None
        if actual != expected:
            mismatches.append({"field": f"values[{coordinate}]", "expected": expected, "actual": actual})
    return ResultEnvelope.ok({**data, "mismatches": mismatches})


def _graph_from_tree(tree: dict[str, Any], ref: str) -> dict[str, Any] | None:
    for graph in tree.get("graphs", []):
        if str(graph.get("name")) == ref or str(graph.get("ref")) == ref:
            return graph
    return None


def _observe(controller: Any, target: AuditTarget) -> tuple[str, Any, list[str]]:
    if target.kind == "file":
        path = Path(target.ref).expanduser().resolve()
        if not path.is_file():
            return "failed", {"exists": False, "path": str(path)}, []
        actual = {"exists": True, "path": str(path), "size": path.stat().st_size}
        minimum = int(target.expected.get("minimum_size", 1))
        mismatches = [] if actual["size"] >= minimum else [
            {"field": "size", "expected": f">={minimum}", "actual": actual["size"]}
        ]
        actual["mismatches"] = mismatches
        return ("failed" if mismatches else "verified"), actual, []
    if target.kind == "worksheet":
        result = _worksheet_check(controller, target)
    elif target.kind == "connector":
        result = controller.manage_connector(worksheet_name=target.ref, action="info")
    elif target.kind == "operation":
        result = controller.get_analysis_operation(operation_ref=target.ref)
    elif target.kind == "graph":
        listed = controller.list_objects()
        if not listed.success:
            result = listed
        else:
            graph = _graph_from_tree(listed.data or {}, target.ref)
            result = (
                ResultEnvelope.ok(graph)
                if graph is not None
                else ResultEnvelope.fail("GRAPH_NOT_FOUND", f"Graph was not found: {target.ref}")
            )
    elif target.kind == "formula":
        reader = getattr(controller, "get_column_formula", None)
        if not callable(reader):
            return "unverified", {"reason": "formula metadata reader is unavailable"}, []
        result = reader(column_ref=target.ref)
    else:
        reader = getattr(controller, "session_status", None)
        if not callable(reader):
            return "unverified", {"reason": "session ownership status is unavailable"}, []
        result = reader()
    if not result.success:
        return "failed", result.to_dict(), list(result.warnings)
    actual = result.data or {}
    expected = {
        key: value
        for key, value in target.expected.items()
        if key not in {"minimum_rows", "representative_values", "minimum_size"}
    }
    existing_mismatches = list(actual.get("mismatches", [])) if isinstance(actual, dict) else []
    mismatches = existing_mismatches + _subset_mismatches(expected, actual)
    status = "failed" if mismatches else ("warning" if result.warnings else "verified")
    if isinstance(actual, dict):
        actual = {**actual, "mismatches": mismatches}
    return status, actual, list(result.warnings)


def run_targeted_audit(
    controller: Any,
    targets: list[AuditTarget],
    *,
    maximum_targets: int = 50,
) -> dict[str, Any]:
    if not targets or len(targets) > maximum_targets:
        raise ValueError("audit requests must contain a bounded target list")
    checks = []
    summary = {"verified": 0, "warning": 0, "unverified": 0, "failed": 0}
    for target in targets:
        status, actual, warnings = _observe(controller, target)
        summary[status] += 1
        checks.append(
            {
                "target": asdict(target),
                "status": status,
                "actual": actual,
                "warnings": warnings,
            }
        )
    return {"success": summary["failed"] == 0, "checks": checks, "summary": summary}

