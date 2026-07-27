"""Legacy FigureSpec adapter over the single WorkflowEngine execution kernel."""

from __future__ import annotations

from typing import Any

from .adapters import figure_to_workflow_spec
from .engine import WorkflowEngine, WorkflowExecutionError
from .figurespec import FigureSpec, figure_spec_digest
from .spec import workflow_spec_digest


class FigureExecutionError(RuntimeError):
    code = "FIGURE_EXECUTION_FAILED"


class _FigureContextAdapter:
    """Bridge the legacy context's small API to WorkflowEngine's richer context."""

    def __init__(self, context: Any) -> None:
        self.context = context

    def stage(self, value: str, **kwargs: Any) -> None:
        self.context.stage(value, mutation=bool(kwargs.get("mutation", False)))

    def complete_stage(self, *, actual: Any = None) -> None:
        if hasattr(self.context, "complete_stage"):
            self.context.complete_stage(actual=actual)

    def fail_stage(
        self, error_code: str, error_message: str, *, actual: Any = None
    ) -> None:
        if hasattr(self.context, "fail_stage"):
            self.context.fail_stage(error_code, error_message, actual=actual)


def _legacy_stage_id(stage: str, spec: FigureSpec) -> str:
    if stage.startswith("import:"):
        return "connector" if spec.route == "data_to_project" and spec.input.source_mode == "linked" else "input"
    if stage.startswith("plot:"):
        return "plot"
    if stage.startswith("analysis:"):
        analysis_id = stage.split(":", 1)[1]
        analysis = next((item for item in spec.analyses if item.id == analysis_id), None)
        if analysis is not None and analysis.backend == "origin_native":
            return "native_operation" if analysis.create_operation else "native_analysis"
        return "analysis"
    return stage


def _legacy_stage_ids(stages: list[str], spec: FigureSpec) -> list[str]:
    result: list[str] = []
    for stage in stages:
        alias = _legacy_stage_id(stage, spec)
        if alias not in result:
            result.append(alias)
    return result


def execute_figure(
    controller: Any,
    spec: FigureSpec,
    *,
    expected_digest: str,
    context: Any,
) -> dict[str, Any]:
    """Execute FigureSpec through WorkflowEngine while preserving legacy result keys."""

    digest = figure_spec_digest(spec)
    if digest != expected_digest:
        raise FigureExecutionError("FigureSpec digest does not match the approved plan")
    workflow_spec = figure_to_workflow_spec(spec)
    workflow_digest = workflow_spec_digest(workflow_spec)
    engine = WorkflowEngine(lambda: controller)
    try:
        receipt = engine.execute(
            workflow_spec,
            expected_digest=workflow_digest,
            idempotency_key=f"figure:{digest}",
            context=_FigureContextAdapter(context),
            validate_artifacts=False,
            require_owned=False,
            verify_import_evidence=False,
            final_qa_worksheet_ref=spec.input.worksheet_ref,
        )
    except (OSError, ValueError, WorkflowExecutionError) as exc:
        raise FigureExecutionError(str(exc)) from exc
    finally:
        engine.close()

    completed = _legacy_stage_ids(list(receipt.get("completed_stages", [])), spec)
    graph_names = {
        key.split(":", 1)[1]: value.get("graph_name", key.split(":", 1)[1])
        for key, value in receipt.get("objects", {}).items()
        if key.startswith("graph:") and isinstance(value, dict)
    }
    result = {
        "success": bool(receipt.get("success")),
        "digest": digest,
        "route": spec.route,
        "completed_stages": completed,
        "artifacts": list(receipt.get("artifacts", [])),
        "warnings": list(receipt.get("warnings", [])),
        "graph_names": graph_names,
    }
    if not receipt.get("success"):
        result.update(
            {
                "failed_stage": _legacy_stage_id(str(receipt.get("failed_stage")), spec),
                "error_code": receipt.get("error_code") or "FIGURE_EXECUTION_FAILED",
                "error_message": receipt.get("error_message") or "Figure workflow failed",
                "data": receipt.get("objects"),
            }
        )
    return result
