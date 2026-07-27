---
name: origin-automation
description: Use when Codex needs to inspect or control OriginLab on Windows through COM, including OPJU projects, worksheets, numerical analysis, LabTalk, graph creation, or graph export.
---

# Origin Automation

Use the MCP tools as the deterministic control surface. Resolve objects by returned names/refs,
preserve the user's scientific choices, and finish through the shortest route that still verifies
the requested result. Prefer one digest-bound WorkflowSpec execution for a clear end-to-end task;
use FigureSpec for the legacy two-route contract and focused tools for exact object-level control.

For new data, preserve editability by default: import with `source_mode="linked"`, create derived
columns with `origin_set_column_formula` so Origin retains the `F(x)` formula, and analyze with
`backend="origin_native"`, `create_operation=true`, and `recalculate_mode="auto"`. Static
`source_mode="snapshot"` and external `backend="python"` are compatibility modes that require an
explicit user choice. Never silently fall back from an unavailable native route to Python.

## Operating Contract

Before the first tool call, form a private task contract containing: task route, source, output, exact analysis method, row/range/branch/filter choices, graph type, and requested artifacts. Do not show a planning preamble when these are already clear. Ask only when a missing value is a scientific choice the user must own or when source overwrite needs explicit authorization; choose routine engineering details yourself.

Do not narrate every MCP call. Give at most a short start update, a genuine blocker update, and the completion report. Continue through routine successful steps without asking for confirmation.

## Task Routing

Choose exactly one primary route and do not mix in diagnostic work unless its trigger occurs:

1. **Environment diagnosis:** `origin_health_check`, report the actionable result, stop. Do not activate Origin.
2. **Read-only active-session inspection/export:** health check, explicit SI/COMSI `origin_start(attach=true)`, targeted audit/read/export, detach with `origin_shutdown`. Never mutate the attached session.
3. **Existing OPJU modification:** health check, owned start, `origin_open_project` working copy, targeted audit, batch read/write/analysis/plot, verify, save a separate copy, shutdown. Never reset workbook templates or page metadata on this route.
4. **New data analysis/plot:** health check, owned start, one `origin_import_data(target_mode="new_workbook", source_mode="linked")`, inspect its connector state and `column_profiles`, native formula/analysis, plot/configure, export or save, shutdown. The import creates a clean sheet from the system installation template instead of the user's customized `Origin.otwu`, then keeps the CSV/Excel Data Connector attached. Skip project opening and broad object audits unless needed for a returned ref.
5. **Complete FigureSpec workflow:** use `origin_inspect_data_source` when column roles need
   preflight, then `origin_plan_figure` and one `origin_execute_figure` with the returned digest.
   Use this route when input, analysis choices, plot roles, OPJU output, exports, and QA fit the
   strict schema. Use `origin_submit_batch` for two or more independent items. Do not expand this
   route into the low-level call sequence unless planning reports a specific unsupported feature.
6. **Intent-aware workflow (preferred for complete tasks):** call `origin_plan_workflow` once with
   the complete source, scientific contract, formulas, analyses, plots, outputs, and QA.
   Ask all `required_decisions` together. Replan once with those answers. Execute one approved digest with
   `origin_execute_workflow` and a unique `idempotency_key`; poll `origin_workflow_status` only
   while queued or running. Use `origin_resume_workflow` only when the ledger exposes a verified
   checkpoint. Finish with bounded `origin_audit_result` targets and `origin_export_manifest`.

For Matrix, Image Page, Data Connector, `F(x)` formula, native operation, template, folder, or Note work, use the
corresponding focused `origin_manage_*` or native-analysis tool inside route 3 or 4. Call
`origin_capabilities(domain=...)` once before a specialized or version-sensitive family; do not
probe by repeatedly executing mutations.

Exporting from a project file uses route 3 and a working copy. Source replacement is not a routine route; use `origin_save_and_replace_source` only with both confirmation booleans and the exact `expected_source_sha256`.

## Fast Critical Path

1. Call `origin_health_check` once and reuse its result.
2. Call `origin_start` once. Default to owned, hidden `Origin.Application`; attach only when the user explicitly targets an already active instance.
3. Open one working copy when a source OPJU is involved.
4. Run one initial `origin_list_objects` only when stable refs or existing structure are needed. Extract all required workbook, worksheet, graph, layer, dimensions, and plot-source facts from that response.
5. Read or import the smallest contiguous blocks that contain all required columns. Import and write tools already perform one exact internal readback; inspect connector state, `readback_verified`, `column_profiles`, `non_empty_count`, and the returned stable `worksheet_ref` instead of adding a reassurance call. If a defining X/Y column is empty, mismatched, or unconfirmed, stop before analysis or plotting.
6. Add derived columns with `origin_set_column_formula`, or `origin_transform_worksheet(action="calculated_column")`, and require formula, script, range, `SVRM`, and value readback confirmation. Materialize values only after the user explicitly selects `execution_mode="materialized"`.
7. Run the exact requested analysis once with explicit row bounds, `row_order`, filters, method, and options. Default to an Origin-native Analysis Operation. If the exact method/options are unavailable natively, stop with the capability error; never substitute Python, a fit, derivative, smoothing, branch, or range.
   Prefer verified native functions over expanded arithmetic when their semantics match. For
   derivatives, select the verified `differentiate` operation contract when compatible;
   `dderivative` requires explicit supported-unverified acceptance. Do not change derivative semantics,
   boundary conventions, branch, range, or point placement merely to reach a native route.
8. Create a graph only if it does not exist. Apply binding, axes, scales, styles, categories, and legend together in one `origin_configure_graph` call per final graph. Prefer structured controls over exploratory LabTalk.
9. Verify only result-defining invariants: record count/values, required column labels, formula/operation state, plot X/Y/label sources, axis state, and non-empty artifacts. Require `label_source_status=resolved` when labels are requested.
10. Run a second `origin_list_objects` only when page structure or plot bindings changed. Analysis-only, formatting-only, and export-only tasks do not need a second audit unless validation fails.
11. Save/export each requested artifact once, verify it, restore any temporary linkage-test edits, then call `origin_shutdown` and require confirmed exit for an owned session.

## Call Budget

- Maximum one health check, one start, one project open, and one initial object audit per task.
- Maximum one write/import plus one readback per logical data block; never write or verify cell by cell.
- Maximum one final configuration call and one normal export/save attempt per requested graph or artifact.
- Reuse returned refs and prior successful responses. Do not repeat successful calls for reassurance.
- Merge adjacent ranges and pass multiple Y columns together when the tool supports it.
- The optional second object audit is reserved for changed structure/bindings or one lookup recovery.
- A FigureSpec job uses one plan and one execution call. Poll `origin_task_status` only for an
  asynchronous submission; do not poll a synchronous execution.
- A WorkflowSpec job uses one successful plan, one approved digest, and one execution submission.
  Never split it into exploratory low-level mutations after approval.
- Query `origin_graph_catalog`, `origin_palette_catalog`, `origin_list_graph_templates`, or
  `origin_query_knowledge` only when their result is needed to choose or validate the requested
  route. They are discovery tools, not routine preambles.

## Conditional Escalation

- **Health/start failure:** inspect registration, bitness, dependencies, process count, and reported cleanup tasks once. Do not run full diagnostics during a healthy task.
- **Object lookup failure:** refresh `origin_list_objects` once, correct the stale name/ref once, then continue.
- **Validation mismatch:** inspect the mismatched data/source/property once and make one targeted correction. Re-run only the failed verification, not the whole workflow.
- **Transient read failure:** rely on the plugin's bounded internal retry. Do not add another manual retry loop.
- **Write, analysis, save, export, timeout, or RPC failure:** never replay blindly. If the same failure repeats after the single targeted correction, stop, safely shut down when possible, and report the exact blocker.
- **First COM timeout:** call `origin_recover_session` immediately. Do not call `origin_shutdown` first because the poisoned STA worker is already blocked. Start a fresh owned session only after recovery, and never replay the timed-out mutation unless the user explicitly authorizes it after inspecting state.
- **FigureSpec planning blocker:** report the exact blocker. Move to focused tools only when the
  requested feature is supported there and the scientific intent remains unchanged; do not weaken
  the spec or set `allow_unverified=true` on the user's behalf.
- Check watchdog/cleanup tasks only after `ORIGIN_PROCESS_TERMINATED`, `CO_E_SERVER_EXEC_FAILURE`, or relevant RPC loss. Never disable or delete them without explicit permission.

## Accuracy And Safety Gates

- Never overwrite a source OPJU by default. Preserve source structure and unrelated pages/data.
- Never mutate an attached session, treat SI/COMSI as owned, infer proxy-PID binding, or terminate Origin by PID.
- Read mixed ranges with `data_format=auto`; use `categorical_label` for category strings and numeric mode only for intended internal numeric values.
- Treat `IMPORT_DATA_LOSS`, `IMPORT_VALIDATION_FAILED`, `WORKSHEET_WRITE_REJECTED`, and `WORKSHEET_WRITE_UNCONFIRMED` as hard stops. Row/column dimensions alone never prove data integrity.
- Keep local CSV/TSV/Excel imports linked unless the user explicitly requests `source_mode="snapshot"`; do not disconnect a successful default connector.
- Keep calculations in Origin with `F(x)` formulas and native Analysis Operations. Use `backend="python"` only when explicitly requested, label it non-recalculating, and never copy external results back as though they were native operations.
- Declare LabTalk outputs with `result_numeric_variables` or `result_string_variables`; a valid empty string remains an empty string.
- Use `categorical_style` and native categorical legends for mapped markers; bind labels directly with `label_column`.
- X-Functions use typed parameters and declared outputs. Set the unverified-function opt-in only
  when the user explicitly chose that exact function and accepts its capability status.
- Graph templates must be discovered first and applied by exact path plus SHA-256. Never treat a
  user workbook template as a graph template or use it implicitly during data import.
- Preview QA requires a nonblank PNG and decisive pixel metrics. Expected colors are evidence of
  rendering, not proof of correct worksheet bindings; verify both when the plot source matters.
- Verify saved/exported files exist, are non-empty, and match the requested format. Do not claim success from a non-throwing COM method alone.
- Temporary editability checks must be restored before saving. Reopen only when persistence/editability is part of the requested acceptance criteria or a high-risk source replacement.

## Completion Format

Return only these compact sections when relevant:

- **Result:** what completed.
- **Method:** exact analysis/range/branch choices.
- **Artifacts:** absolute paths.
- **Verification:** decisive counts, bindings, file checks, and shutdown state.
- **Limitations:** only genuine unverified or blocked items; omit when empty.
