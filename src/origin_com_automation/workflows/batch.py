"""Deterministic serial batch planning and execution."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


class BatchPlanError(ValueError):
    code = "BATCH_PLAN_INVALID"


@dataclass(frozen=True)
class BatchItem:
    index: int
    input_path: str
    input_sha256: str
    output_dir: str


@dataclass(frozen=True)
class BatchPlan:
    items: tuple[BatchItem, ...]
    output_root: str


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def build_batch_plan(
    *,
    files: list[str],
    output_root: str,
    preserve_order: bool = True,
) -> BatchPlan:
    if not files:
        raise BatchPlanError("batch files cannot be empty")
    resolved = [Path(item).expanduser().resolve() for item in files]
    if len(set(resolved)) != len(resolved):
        raise BatchPlanError("batch files must be unique")
    if any(not item.is_file() for item in resolved):
        raise BatchPlanError("every batch input must exist")
    if not preserve_order:
        resolved.sort(key=lambda item: str(item).casefold())
    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    items: list[BatchItem] = []
    used: set[Path] = set()
    for index, source in enumerate(resolved, start=1):
        candidate = root / f"{index:04d}-{source.stem}"
        if candidate in used or candidate.exists():
            raise BatchPlanError(f"batch output collision: {candidate}")
        used.add(candidate)
        items.append(
            BatchItem(
                index=index,
                input_path=str(source),
                input_sha256=_sha256(source),
                output_dir=str(candidate),
            )
        )
    return BatchPlan(tuple(items), str(root))


def execute_batch(
    plan: BatchPlan,
    executor: Callable[[BatchItem], dict[str, Any]],
    *,
    fail_fast: bool = True,
    on_error: str | None = None,
) -> dict[str, Any]:
    if on_error is not None:
        if on_error not in {"stop", "continue"}:
            raise BatchPlanError("on_error must be stop or continue")
        fail_fast = on_error == "stop"
    results: list[dict[str, Any]] = []
    stopped = False
    failed_item: dict[str, Any] | None = None
    for item in plan.items:
        Path(item.output_dir).mkdir(parents=True, exist_ok=False)
        result = executor(item)
        results.append({"item": item.__dict__, "result": result})
        if not result.get("success", False) and fail_fast:
            stopped = True
            failed_item = item.__dict__
            break
    return {
        "total": len(plan.items),
        "completed": len(results),
        "stopped_early": stopped,
        "failed_item": failed_item,
        "results": results,
    }
