"""Fail-fast FigureSpec executor over public controller methods."""

from __future__ import annotations

from typing import Any

from ..contracts import ResultEnvelope
from .engine import report_context_result
from .figurespec import FigureSpec, compile_figure_spec, figure_spec_digest


class FigureExecutionError(RuntimeError):
    code = "FIGURE_EXECUTION_FAILED"


def execute_figure(
    controller: Any,
    spec: FigureSpec,
    *,
    expected_digest: str,
    context: Any,
) -> dict[str, Any]:
    digest = figure_spec_digest(spec)
    if digest != expected_digest:
        raise FigureExecutionError("FigureSpec digest does not match the approved plan")
    context.stage("preflight", mutation=False)
    plan = compile_figure_spec(
        spec,
        origin_version=getattr(controller, "origin_version", None),
    )
    if not plan["executor_executable"]:
        raise FigureExecutionError("; ".join(plan["blockers"]))
    report_context_result(context, ResultEnvelope.ok({"digest": digest}))

    completed: list[str] = ["preflight"]
    artifacts: list[dict[str, str]] = []
    warnings: list[str] = list(plan["warnings"])
    failed: dict[str, Any] | None = None
    session_started = False

    def run(stage: str, function, *, mutation: bool = True) -> ResultEnvelope:
        nonlocal failed
        context.stage(stage, mutation=mutation)
        result: ResultEnvelope = function()
        report_context_result(context, result)
        artifacts.extend(item.to_dict() for item in result.artifacts)
        warnings.extend(result.warnings)
        if result.success:
            if stage not in completed:
                completed.append(stage)
        else:
            failed = {
                "failed_stage": stage,
                "error_code": result.error_code,
                "error_message": result.error_message,
                "data": result.data,
            }
        return result

    try:
        started = run("start", lambda: controller.start(visible=spec.visible, attach=False))
        if not started.success:
            return {"success": False, **failed, "completed_stages": completed, "artifacts": artifacts, "warnings": warnings}
        session_started = True

        if spec.route == "data_to_project":
            input_stage = "connector" if spec.input.source_mode == "linked" else "input"
            input_result = run(
                input_stage,
                lambda: controller.import_data(
                    file_path=plan["resolved_input"],
                    worksheet_name=spec.input.worksheet_ref,
                    sheet_name=spec.input.sheet_name,
                    has_header=spec.input.has_header,
                    target_mode="new_workbook",
                    source_mode=spec.input.source_mode,
                ),
            )
        else:
            input_result = run(
                "input",
                lambda: controller.open_project(source_path=plan["resolved_input"]),
            )
        if not input_result.success:
            return {"success": False, **failed, "completed_stages": completed, "artifacts": artifacts, "warnings": warnings}

        for analysis in spec.analyses:
            if analysis.backend == "origin_native" and analysis.create_operation:
                analysis_stage = "native_operation"
            elif analysis.backend == "origin_native":
                analysis_stage = "native_analysis"
            else:
                analysis_stage = "analysis"
            result = run(
                analysis_stage,
                lambda analysis=analysis: controller.run_analysis(
                    worksheet_name=analysis.worksheet_ref,
                    method=analysis.method,
                    x_column=analysis.x_column,
                    y_column=analysis.y_column,
                    options={
                        **analysis.options,
                        "backend": analysis.backend,
                        "create_operation": analysis.create_operation,
                        "recalculate_mode": analysis.recalculate_mode,
                    },
                    row_start=analysis.row_start,
                    row_end=analysis.row_end,
                ),
            )
            if not result.success:
                return {"success": False, **failed, "completed_stages": completed, "artifacts": artifacts, "warnings": warnings}

        graph_names: dict[str, str] = {}
        for plot in spec.plots:
            result = run(
                "plot",
                lambda plot=plot: controller.create_graph(
                    graph_type=plot.graph_type,
                    roles=plot.roles,
                    graph_name=plot.graph_name,
                    allow_unverified=plot.allow_unverified,
                ),
            )
            if not result.success:
                return {"success": False, **failed, "completed_stages": completed, "artifacts": artifacts, "warnings": warnings}
            graph_names[plot.id] = plot.graph_name or str((result.data or {}).get("graph_name") or plot.id)

        saved = run(
            "save",
            lambda: controller.save_project_copy(
                target_path=plan["resolved_project_output"],
                overwrite=spec.outputs.overwrite == "replace",
            ),
        )
        if not saved.success:
            return {"success": False, **failed, "completed_stages": completed, "artifacts": artifacts, "warnings": warnings}

        for export in spec.outputs.exports:
            result = run(
                "export",
                lambda export=export: controller.export_graph(
                    graph_name=graph_names[export.graph_id],
                    output_path=export.path,
                    export_format=export.format,
                    overwrite="replace" if spec.outputs.overwrite == "replace" else "skip",
                ),
            )
            if not result.success:
                return {"success": False, **failed, "completed_stages": completed, "artifacts": artifacts, "warnings": warnings}

        qa_ref = spec.input.worksheet_ref
        if qa_ref:
            qa = run(
                "qa",
                lambda: controller.read_worksheet(qa_ref, data_format="variant"),
                mutation=False,
            )
            if not qa.success:
                return {"success": False, **failed, "completed_stages": completed, "artifacts": artifacts, "warnings": warnings}
            values = (qa.data or {}).get("values", [])
            if len(values) < spec.qa.minimum_rows:
                failed = {
                    "failed_stage": "qa",
                    "error_code": "FIGURE_QA_FAILED",
                    "error_message": "Worksheet row count is below minimum_rows",
                    "data": {"rows": len(values), "minimum_rows": spec.qa.minimum_rows},
                }
                return {"success": False, **failed, "completed_stages": completed, "artifacts": artifacts, "warnings": warnings}
        elif "qa" not in completed:
            completed.append("qa")

        return {
            "success": True,
            "digest": digest,
            "route": spec.route,
            "completed_stages": completed,
            "artifacts": artifacts,
            "warnings": warnings,
            "graph_names": graph_names,
        }
    finally:
        if session_started:
            context.stage("shutdown", mutation=True)
            shutdown = controller.shutdown()
            report_context_result(context, shutdown)
            artifacts.extend(item.to_dict() for item in shutdown.artifacts)
            warnings.extend(shutdown.warnings)
            if shutdown.success and "shutdown" not in completed:
                completed.append("shutdown")
