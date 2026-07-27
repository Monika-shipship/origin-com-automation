"""Digest-bound, resumable execution for intent-aware Origin workflows."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

from .. import __version__
from ..contracts import ResultEnvelope
from ..utils.hashing import sha256_file
from ..utils.runtime import controller_origin_version
from .manifest import build_workflow_manifest, write_manifest_artifacts
from .planner import PlannedStage, WorkflowPlan, compile_workflow
from .spec import WorkflowSpec, workflow_spec_digest
from .tasks import TaskManager


class WorkflowExecutionError(RuntimeError):
    code = "WORKFLOW_EXECUTION_REJECTED"


def _result_data(result: ResultEnvelope) -> dict[str, Any]:
    return result.data if isinstance(result.data, dict) else {"value": result.data}


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(temporary, path)


_sha256 = sha256_file


def _import_target_name(worksheet_ref: str | None, source_id: str) -> str:
    if worksheet_ref and worksheet_ref.startswith("[") and "]" in worksheet_ref:
        page = worksheet_ref[1 : worksheet_ref.index("]")].strip()
        if page:
            return page
    return (worksheet_ref or source_id).strip()


def report_context_result(context: Any, result: ResultEnvelope) -> None:
    """Report a stage result to old or new task contexts without schema drift."""

    if context is None:
        return
    if result.success and hasattr(context, "complete_stage"):
        context.complete_stage(actual=result.data)
    elif not result.success and hasattr(context, "fail_stage"):
        context.fail_stage(
            result.error_code or "WORKFLOW_STAGE_FAILED",
            result.error_message or "Workflow stage failed",
            actual=result.data,
        )


class WorkflowEngine:
    """Execute immutable plans over the existing public ``OriginController`` API."""

    def __init__(
        self,
        controller_factory: Callable[[], Any],
        *,
        task_manager: TaskManager | None = None,
    ) -> None:
        self.controller_factory = controller_factory
        self.tasks = task_manager or TaskManager()

    def close(self) -> None:
        self.tasks.shutdown()

    def plan(
        self,
        spec: WorkflowSpec,
        *,
        origin_version: str | None = None,
    ) -> WorkflowPlan:
        return compile_workflow(spec, origin_version=origin_version)

    def submit(
        self,
        spec: WorkflowSpec,
        *,
        expected_digest: str,
        idempotency_key: str,
    ) -> str:
        return self.tasks.submit(
            "origin_workflow",
            lambda context: self.execute(
                spec,
                expected_digest=expected_digest,
                idempotency_key=idempotency_key,
                context=context,
            ),
            idempotency_key=idempotency_key,
        )

    def submit_resume(
        self,
        spec: WorkflowSpec,
        *,
        expected_digest: str,
        idempotency_key: str,
    ) -> str:
        _, ledger_path = self._paths(spec, idempotency_key)
        if not ledger_path.is_file():
            raise WorkflowExecutionError("workflow ledger does not exist")
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        attempt = str(ledger.get("updated_at", ledger_path.stat().st_mtime_ns))
        resume_key = hashlib.sha256(
            f"resume:{idempotency_key}:{attempt}".encode("utf-8")
        ).hexdigest()
        return self.tasks.submit(
            "origin_workflow_resume",
            lambda context: self.resume(
                spec,
                expected_digest=expected_digest,
                idempotency_key=idempotency_key,
                context=context,
            ),
            idempotency_key=resume_key,
        )

    def status(self, task_id: str) -> dict[str, Any]:
        return self.tasks.read_status(task_id)

    def _paths(self, spec: WorkflowSpec, idempotency_key: str) -> tuple[Path, Path]:
        output = Path(spec.outputs.project_path).expanduser().resolve()
        key = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:12]
        root = output.parent / ".origin-com-automation" / f"{output.stem}-{key}"
        return root, root / "ledger.json"

    def _new_ledger(
        self,
        spec: WorkflowSpec,
        plan: WorkflowPlan,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "digest": plan.digest,
            "idempotency_key": idempotency_key,
            "source_hashes": dict(plan.derived_values.get("source_hashes", {})),
            "output_project": plan.resolved_project_output,
            "state": "running",
            "created_at": time.time(),
            "updated_at": time.time(),
            "stages": [],
            "completed_stage_ids": [],
            "completed_mutation_keys": [],
            "objects": {},
            "checkpoints": [],
            "warnings": [],
            "artifacts": [],
            "failure": None,
            "spec": spec.model_dump(mode="json", exclude_none=True),
        }

    @staticmethod
    def _record_stage(
        ledger: dict[str, Any],
        stage: PlannedStage,
        *,
        state: str,
        actual: Any = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        ledger["stages"].append(
            {
                "stage_id": stage.id,
                "state": state,
                "mutation": stage.mutation,
                "idempotency_key": stage.idempotency_key,
                "object_ref": stage.target,
                "actual": actual,
                "error_code": error_code,
                "error_message": error_message,
            }
        )
        ledger["updated_at"] = time.time()
        if state == "completed":
            if stage.id not in ledger["completed_stage_ids"]:
                ledger["completed_stage_ids"].append(stage.id)
            if (
                stage.mutation
                and stage.idempotency_key
                and stage.idempotency_key not in ledger["completed_mutation_keys"]
            ):
                ledger["completed_mutation_keys"].append(stage.idempotency_key)

    @staticmethod
    def _context_start(context: Any, stage: PlannedStage) -> None:
        if context is not None:
            context.stage(
                stage.id,
                mutation=stage.mutation,
                idempotency_key=stage.idempotency_key,
                object_ref=stage.target,
            )

    @staticmethod
    def _context_complete(context: Any, actual: Any) -> None:
        report_context_result(context, ResultEnvelope.ok(actual))

    @staticmethod
    def _context_fail(context: Any, result: ResultEnvelope) -> None:
        report_context_result(context, result)

    def _checkpoint(
        self,
        controller: Any,
        root: Path,
        ledger: dict[str, Any],
        phase: str,
    ) -> ResultEnvelope:
        path = root / f"checkpoint-{len(ledger['checkpoints']) + 1:02d}-{phase}.opju"
        result = controller.save_project_copy(target_path=str(path), overwrite=False)
        if not result.success:
            return result
        if not path.is_file() or path.stat().st_size < 8:
            return ResultEnvelope.fail(
                "CHECKPOINT_VALIDATION_FAILED",
                f"Checkpoint was not created or is too small: {path}",
            )
        ledger["checkpoints"].append(
            {
                "phase": phase,
                "path": str(path),
                "sha256": _sha256(path),
                "completed_stage_ids": list(ledger["completed_stage_ids"]),
                "completed_mutation_keys": list(ledger["completed_mutation_keys"]),
            }
        )
        return result

    @staticmethod
    def _verify_sources(plan: WorkflowPlan, ledger: dict[str, Any] | None = None) -> None:
        actual = dict(plan.derived_values.get("source_hashes", {}))
        if ledger is not None and actual != ledger.get("source_hashes", {}):
            raise WorkflowExecutionError("source hashes changed since the approved plan")

    @staticmethod
    def _validate_plan(spec: WorkflowSpec, expected_digest: str, plan: WorkflowPlan) -> None:
        if workflow_spec_digest(spec) != expected_digest or plan.digest != expected_digest:
            raise WorkflowExecutionError("workflow digest does not match the approved plan")
        if plan.required_decisions:
            fields = ", ".join(item["field"] for item in plan.required_decisions)
            raise WorkflowExecutionError(
                f"required scientific decisions are unresolved: {fields}"
            )
        if plan.blockers:
            codes = ", ".join(item.get("code", "BLOCKED") for item in plan.blockers)
            raise WorkflowExecutionError(f"workflow plan is blocked: {codes}")

    def execute(
        self,
        spec: WorkflowSpec,
        *,
        expected_digest: str,
        idempotency_key: str,
        context: Any = None,
        _resume: bool = False,
        validate_artifacts: bool = True,
        require_owned: bool = True,
        verify_import_evidence: bool = True,
        final_qa_worksheet_ref: str | None = None,
    ) -> dict[str, Any]:
        if not idempotency_key.strip():
            raise WorkflowExecutionError("idempotency key is required")
        plan = self.plan(spec)
        self._validate_plan(spec, expected_digest, plan)
        root, ledger_path = self._paths(spec, idempotency_key)
        checkpoint_policy = str(
            plan.safe_defaults.get(
                "resolved_checkpoint_policy", spec.execution.checkpoint_policy
            )
        )
        milestone_after = plan.safe_defaults.get("milestone_after")
        eager_ledger_writes = checkpoint_policy in {"phase", "mutation"}

        if _resume:
            if not ledger_path.is_file():
                raise WorkflowExecutionError("workflow ledger does not exist")
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            if ledger.get("digest") != expected_digest:
                raise WorkflowExecutionError("workflow ledger digest does not match")
            self._verify_sources(plan, ledger)
            checkpoints = ledger.get("checkpoints", [])
            if not checkpoints:
                raise WorkflowExecutionError("no verified checkpoint is available for resume")
            checkpoint = checkpoints[-1]
            checkpoint_path = Path(checkpoint["path"])
            if not checkpoint_path.is_file() or _sha256(checkpoint_path) != checkpoint["sha256"]:
                raise WorkflowExecutionError("workflow checkpoint hash does not match")
            ledger["state"] = "running"
            ledger["failure"] = None
        else:
            if ledger_path.exists():
                previous = json.loads(ledger_path.read_text(encoding="utf-8"))
                if previous.get("state") == "succeeded":
                    raise WorkflowExecutionError(
                        "idempotency key already completed; use the prior result"
                    )
            self._verify_sources(plan)
            ledger = self._new_ledger(spec, plan, idempotency_key)

        _atomic_json(ledger_path, ledger)
        controller = self.controller_factory()
        session_started = False
        failed_stage: str | None = None
        failure: ResultEnvelope | None = None
        phase_dirty = False
        graph_names: dict[str, str] = {
            key.removeprefix("graph:"): value.get("graph_name", key.removeprefix("graph:"))
            for key, value in ledger["objects"].items()
            if key.startswith("graph:") and isinstance(value, dict)
        }
        worksheet_refs: dict[str, str] = {}
        for source in spec.sources:
            observed = ledger["objects"].get(f"worksheet:{source.id}", {})
            actual_ref = observed.get("worksheet_ref") if isinstance(observed, dict) else None
            if source.worksheet_ref and actual_ref:
                worksheet_refs[source.worksheet_ref] = str(actual_ref)

        def resolve_worksheet(value: str) -> str:
            return worksheet_refs.get(value, value)

        def finish_stage(stage: PlannedStage, result: ResultEnvelope) -> bool:
            nonlocal failed_stage, failure, phase_dirty
            ledger["warnings"].extend(result.warnings)
            ledger["artifacts"].extend(item.to_dict() for item in result.artifacts)
            if not result.success:
                failed_stage = stage.id
                failure = result
                self._record_stage(
                    ledger,
                    stage,
                    state="failed",
                    actual=result.data,
                    error_code=result.error_code,
                    error_message=result.error_message,
                )
                self._context_fail(context, result)
                _atomic_json(ledger_path, ledger)
                return False
            actual = _result_data(result)
            self._record_stage(ledger, stage, state="completed", actual=actual)
            self._context_complete(context, actual)
            if stage.target:
                ledger["objects"][stage.target] = actual
            phase_dirty = phase_dirty or stage.mutation
            if eager_ledger_writes:
                _atomic_json(ledger_path, ledger)
            return True

        def checkpoint_after(phase: str) -> bool:
            nonlocal failed_stage, failure, phase_dirty
            if checkpoint_policy == "none" or not phase_dirty:
                return True
            result = self._checkpoint(controller, root, ledger, phase)
            if not result.success:
                failed_stage = f"checkpoint:{phase}"
                failure = result
                ledger["failure"] = {
                    "stage": failed_stage,
                    "error_code": result.error_code,
                    "error_message": result.error_message,
                }
                _atomic_json(ledger_path, ledger)
                return False
            phase_dirty = False
            _atomic_json(ledger_path, ledger)
            return True

        try:
            for stage in plan.stages:
                if stage.id == "shutdown":
                    continue
                if _resume and stage.id not in {"start"} and stage.id in ledger["completed_stage_ids"]:
                    continue
                if (
                    _resume
                    and stage.id != "start"
                    and stage.mutation
                    and stage.idempotency_key in ledger["completed_mutation_keys"]
                ):
                    continue
                self._context_start(context, stage)

                if stage.id == "preflight":
                    result = ResultEnvelope.ok({"digest": plan.digest, "source_hashes": ledger["source_hashes"]})
                elif stage.id == "start":
                    result = controller.start(visible=spec.visible, attach=False, exclusive=False)
                    if result.success:
                        session_started = bool(_result_data(result).get("owned")) or (
                            result.success and not require_owned
                        )
                        if not session_started and require_owned:
                            result = ResultEnvelope.fail(
                                "SESSION_NOT_OWNED",
                                "Workflow execution requires a plugin-owned Origin instance",
                                data=result.data,
                            )
                        elif _resume:
                            checkpoint = ledger["checkpoints"][-1]
                            opened = controller.open_project(source_path=checkpoint["path"])
                            if not opened.success:
                                result = opened
                elif stage.id == "prepare_copy":
                    result = ResultEnvelope.ok({"mode": "new_plugin_owned_project"})
                elif stage.id.startswith("import:"):
                    source_id = stage.id.split(":", 1)[1]
                    source = next(item for item in spec.sources if item.id == source_id)
                    if source.import_mode == "project":
                        imported = controller.open_project(source_path=source.path)
                    else:
                        imported = controller.import_data(
                            file_path=source.path,
                            worksheet_name=_import_target_name(source.worksheet_ref, source.id),
                            sheet_name=source.sheet_name,
                            has_header=source.has_header,
                            target_mode="new_workbook",
                            source_mode="linked" if source.import_mode != "snapshot" else "snapshot",
                        )
                    if imported.success:
                        if source.import_mode == "project":
                            result = ResultEnvelope.ok(
                                {
                                    **_result_data(imported),
                                    "project_ref": source.path,
                                },
                                warnings=imported.warnings,
                                artifacts=imported.artifacts,
                            )
                            if source.worksheet_ref:
                                worksheet_refs[source.worksheet_ref] = source.worksheet_ref
                            # A project input is already a validated working copy source;
                            # there is no worksheet import evidence to read here.
                            imported = result

                        imported_data = _result_data(imported)
                        worksheet_ref = imported_data.get("worksheet_ref") or source.worksheet_ref
                        verified_rows = imported_data.get("verified_rows")
                        if not isinstance(verified_rows, int):
                            rows = imported_data.get("rows")
                            verified_rows = rows if isinstance(rows, int) else None
                        if source.import_mode == "project":
                            pass
                        elif verified_rows is not None:
                            if verified_rows < spec.qa.minimum_rows:
                                result = ResultEnvelope.fail(
                                    "WORKFLOW_DATA_VERIFICATION_FAILED",
                                    "Imported worksheet is below the required row count",
                                    data={"worksheet_ref": worksheet_ref, "rows": verified_rows},
                                )
                            else:
                                if source.worksheet_ref:
                                    worksheet_refs[source.worksheet_ref] = str(worksheet_ref)
                                result = ResultEnvelope.ok(
                                    {**imported_data, "verified_rows": verified_rows},
                                    warnings=imported.warnings,
                                    artifacts=imported.artifacts,
                                )
                        elif verify_import_evidence:
                            verified = controller.read_worksheet(
                                worksheet_ref, data_format="variant"
                            )
                            if not verified.success:
                                result = verified
                            else:
                                values = _result_data(verified).get("values", [])
                                verified_rows = len(values)
                                if verified_rows < spec.qa.minimum_rows:
                                    result = ResultEnvelope.fail(
                                        "WORKFLOW_DATA_VERIFICATION_FAILED",
                                        "Imported worksheet is below the required row count",
                                        data={
                                            "worksheet_ref": worksheet_ref,
                                            "rows": verified_rows,
                                        },
                                    )
                                else:
                                    if source.worksheet_ref:
                                        worksheet_refs[source.worksheet_ref] = str(worksheet_ref)
                                    result = ResultEnvelope.ok(
                                        {
                                            **imported_data,
                                            "verified_rows": verified_rows,
                                        },
                                        warnings=imported.warnings + verified.warnings,
                                        artifacts=imported.artifacts + verified.artifacts,
                                    )
                        else:
                            if source.worksheet_ref:
                                worksheet_refs[source.worksheet_ref] = str(worksheet_ref)
                            result = ResultEnvelope.ok(
                                imported_data,
                                warnings=imported.warnings,
                                artifacts=imported.artifacts,
                            )
                    else:
                        result = imported
                elif stage.id == "verify_data":
                    result = ResultEnvelope.ok({"verified_sources": len(spec.sources)})
                elif stage.id.startswith("formula:"):
                    formula_id = stage.id.split(":", 1)[1]
                    formula = next(item for item in spec.formulas if item.id == formula_id)
                    expression = formula.formula
                    if expression is None:
                        arguments = ",".join(str(value) for value in formula.arguments.values())
                        expression = f"{formula.native_function}({arguments})"
                    result = controller.set_column_formula(
                        worksheet_ref=resolve_worksheet(formula.worksheet_ref),
                        column=formula.column,
                        formula=expression,
                        recalculate_mode=formula.recalculate_mode,
                    )
                elif stage.id.startswith("analysis:"):
                    analysis_id = stage.id.split(":", 1)[1]
                    analysis = next(item for item in spec.analyses if item.id == analysis_id)
                    outputs = []
                    result = ResultEnvelope.ok({})
                    for y_column in analysis.y_columns:
                        analysis_options = dict(analysis.options)
                        if analysis.method.strip().lower() == "derivative":
                            if spec.scientific_contract.derivative_method is not None:
                                analysis_options.setdefault(
                                    "derivative_method",
                                    spec.scientific_contract.derivative_method,
                                )
                            if spec.scientific_contract.derivative_order is not None:
                                analysis_options.setdefault(
                                    "order", spec.scientific_contract.derivative_order
                                )
                        candidate = controller.run_analysis(
                            worksheet_name=resolve_worksheet(analysis.worksheet_ref),
                            method=analysis.method,
                            x_column=analysis.x_column,
                            y_column=y_column,
                            options={
                                **analysis_options,
                                "backend": "python" if analysis.backend_policy == "external_explicit" else "origin_native",
                                "create_operation": analysis.create_operation,
                                "recalculate_mode": analysis.recalculate_mode,
                            },
                        )
                        if not candidate.success:
                            result = candidate
                            break
                        outputs.append(_result_data(candidate))
                    if result.success:
                        result = ResultEnvelope.ok(outputs[0] if len(outputs) == 1 else {"outputs": outputs})
                elif stage.id.startswith("plot:"):
                    plot_id = stage.id.split(":", 1)[1]
                    plot = next(item for item in spec.plots if item.id == plot_id)
                    roles = dict(plot.roles)
                    worksheet_role = roles.get("worksheet")
                    if isinstance(worksheet_role, str):
                        roles["worksheet"] = resolve_worksheet(worksheet_role)
                    created = controller.create_graph(
                        graph_type=plot.graph_type,
                        roles=roles,
                        graph_name=plot.graph_name,
                        allow_unverified=plot.allow_unverified,
                    )
                    result = created
                    if result.success:
                        graph_names[plot.id] = str(_result_data(result).get("graph_name") or plot.graph_name or plot.id)
                elif stage.id == "save":
                    result = controller.save_project_copy(
                        target_path=plan.resolved_project_output,
                        overwrite=spec.outputs.overwrite == "replace",
                    )
                    if result.success:
                        path = Path(plan.resolved_project_output)
                        if validate_artifacts and (not path.is_file() or path.stat().st_size < 8):
                            result = ResultEnvelope.fail(
                                "PROJECT_SAVE_UNCONFIRMED",
                                f"Saved project was not found or was too small: {path}",
                            )
                        elif final_qa_worksheet_ref:
                            verified = controller.read_worksheet(
                                resolve_worksheet(final_qa_worksheet_ref),
                                data_format="variant",
                            )
                            if not verified.success:
                                result = verified
                            else:
                                values = _result_data(verified).get("values", [])
                                if len(values) < spec.qa.minimum_rows:
                                    result = ResultEnvelope.fail(
                                        "WORKFLOW_DATA_VERIFICATION_FAILED",
                                        "Worksheet row count is below minimum_rows",
                                        data={
                                            "rows": len(values),
                                            "minimum_rows": spec.qa.minimum_rows,
                                        },
                                    )
                elif stage.id.startswith("export:"):
                    _, graph_id, export_format = stage.id.split(":", 2)
                    export = next(item for item in spec.outputs.exports if item.graph_id == graph_id and item.format == export_format)
                    result = controller.export_graph(
                        graph_name=graph_names[graph_id],
                        output_path=export.path,
                        export_format=export.format,
                        overwrite="replace" if spec.outputs.overwrite == "replace" else "skip",
                    )
                elif stage.id == "reopen_audit":
                    result = controller.list_objects()
                elif stage.id == "manifest":
                    manifest = build_workflow_manifest(
                        spec,
                        plan,
                        ledger,
                        plugin_version=__version__,
                        origin_version=controller_origin_version(
                            controller,
                            default=plan.origin_version,
                        ),
                    )
                    local_formats = [
                        item for item in spec.outputs.manifest_formats if item in {"json", "text"}
                    ]
                    artifacts = write_manifest_artifacts(
                        manifest,
                        root / "workflow-manifest",
                        formats=local_formats,
                    )
                    warnings = []
                    note_result: ResultEnvelope | None = None
                    if "notes" in spec.outputs.manifest_formats:
                        note_writer = getattr(controller, "manage_note", None)
                        if callable(note_writer):
                            note_result = note_writer(
                                action="create",
                                note_ref="Codex Workflow Manifest",
                                text=json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
                                format="text",
                            )
                            if not note_result.success and note_result.error_code == "NOTE_ALREADY_EXISTS":
                                note_result = note_writer(
                                    action="write",
                                    note_ref="Codex Workflow Manifest",
                                    text=json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
                                    format="text",
                                )
                        else:
                            warnings.append(
                                "Origin Notes manifest was not created because the controller does not expose manage_note"
                            )
                    if note_result is not None and not note_result.success:
                        result = note_result
                    else:
                        result = ResultEnvelope.ok(
                            {
                                "digest": plan.digest,
                                "source_hashes": ledger["source_hashes"],
                                "object_refs": sorted(ledger["objects"]),
                                "formats": list(spec.outputs.manifest_formats),
                            },
                            warnings=warnings + (note_result.warnings if note_result else []),
                            artifacts=artifacts + (note_result.artifacts if note_result else []),
                        )
                else:
                    result = ResultEnvelope.fail(
                        "WORKFLOW_STAGE_UNKNOWN", f"Unsupported planned stage: {stage.id}"
                    )

                if not finish_stage(stage, result):
                    break
                if checkpoint_policy == "mutation" and stage.mutation:
                    if not checkpoint_after(stage.id.replace(":", "-")):
                        break
                elif checkpoint_policy == "phase":
                    if stage.id == "verify_data" and not checkpoint_after("data"):
                        break
                    if stage.id.startswith("analysis:") and not checkpoint_after("analysis"):
                        break
                    if stage.id.startswith("plot:") and not checkpoint_after("plot"):
                        break
                    if stage.id == "manifest" and not checkpoint_after("manifest"):
                        break
                elif checkpoint_policy == "milestone":
                    reached_milestone = (
                        milestone_after == "data" and stage.id == "verify_data"
                    ) or (
                        milestone_after == "analysis"
                        and stage.id.startswith("analysis:")
                        and stage.id
                        == next(
                            candidate.id
                            for candidate in reversed(plan.stages)
                            if candidate.id.startswith("analysis:")
                        )
                    )
                    if reached_milestone and not checkpoint_after(str(milestone_after)):
                        break
        finally:
            if session_started:
                shutdown_stage = next(stage for stage in plan.stages if stage.id == "shutdown")
                self._context_start(context, shutdown_stage)
                shutdown = controller.shutdown()
                finish_stage(shutdown_stage, shutdown)

        if failure is None and failed_stage is None:
            ledger["state"] = "succeeded"
            ledger["failure"] = None
        else:
            ledger["state"] = "failed"
            ledger["failure"] = {
                "stage": failed_stage,
                "error_code": failure.error_code if failure else "WORKFLOW_STAGE_FAILED",
                "error_message": failure.error_message if failure else "Workflow stage failed",
                "data": failure.data if failure else None,
            }
        _atomic_json(ledger_path, ledger)
        return {
            "success": ledger["state"] == "succeeded",
            "digest": plan.digest,
            "idempotency_key": idempotency_key,
            "completed_stages": list(ledger["completed_stage_ids"]),
            "objects": dict(ledger["objects"]),
            "checkpoints": list(ledger["checkpoints"]),
            "ledger_path": str(ledger_path),
            "warnings": list(ledger["warnings"]),
            "artifacts": list(ledger["artifacts"]),
            "failed_stage": failed_stage,
            "error_code": failure.error_code if failure else None,
            "error_message": failure.error_message if failure else None,
        }

    def resume(
        self,
        spec: WorkflowSpec,
        *,
        expected_digest: str,
        idempotency_key: str,
        context: Any = None,
        validate_artifacts: bool = True,
        require_owned: bool = True,
        verify_import_evidence: bool = True,
        final_qa_worksheet_ref: str | None = None,
    ) -> dict[str, Any]:
        return self.execute(
            spec,
            expected_digest=expected_digest,
            idempotency_key=idempotency_key,
            context=context,
            _resume=True,
            validate_artifacts=validate_artifacts,
            require_owned=require_owned,
            verify_import_evidence=verify_import_evidence,
            final_qa_worksheet_ref=final_qa_worksheet_ref,
        )
