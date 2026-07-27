# Intent-Aware Origin Workflow System 0.3.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver Origin COM Automation 0.3.0 with a shared intent-aware workflow kernel,
scientific parameter contracts, offline preflight, fail-fast and idempotent execution, native
expression selection, targeted verification, reproducibility manifests, and complete release
history.

**Architecture:** Add an orchestration layer over the existing controllers and serialized COM
worker. Strict Pydantic specifications compile into digest-bound plans; a stage ledger executes
only approved mutations, uses structured object references, and verifies every deliverable. The
existing low-level tools and FigureSpec routes remain compatible and reuse the same controllers.

**Tech Stack:** Python 3.11+, Pydantic 2, FastMCP, pywin32, Origin COM/LabTalk/X-Functions,
pytest, Pillow/NumPy, Ruff, mypy.

---

### Task 1: Workflow specification and scientific decision contract

**Files:**
- Create: `src/origin_com_automation/workflows/spec.py`
- Modify: `src/origin_com_automation/workflows/__init__.py`
- Test: `tests/unit/test_workflow_spec.py`

- [ ] **Step 1: Write failing strict-schema tests**

Add tests that construct `WorkflowSpec` with `intent="fit_and_plot"`, one linked source, explicit
column roles, a linear-fit analysis, graph output, and no-overwrite project output. Assert extra
fields fail, scientific choices are represented by `ScientificContract`, and changing branch,
range, method, units, or backend policy changes `workflow_spec_digest()`.

- [ ] **Step 2: Verify the schema tests fail**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_workflow_spec.py -q`

Expected: collection fails because `origin_com_automation.workflows.spec` does not exist.

- [ ] **Step 3: Implement the strict models and digest**

Define `StrictModel(extra="forbid")`, `SourceSpec`, `RowSelection`, `ColumnRoles`,
`ScientificContract`, `FormulaStep`, `AnalysisStep`, `PlotStep`, `WorkflowOutputs`,
`ExecutionPolicy`, `WorkflowQA`, and `WorkflowSpec`. Use closed literals for intents, import modes,
branch/order policies, backend policies, overwrite policies, and verification levels. Compute the
digest from canonical JSON with sorted keys and excluded `None` values.

- [ ] **Step 4: Run the focused tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_workflow_spec.py -q`

Expected: all workflow-spec tests pass.

Commit: `git add src/origin_com_automation/workflows/spec.py src/origin_com_automation/workflows/__init__.py tests/unit/test_workflow_spec.py && git commit -m "Add strict workflow specification contract"`

### Task 2: Robust offline source preview

**Files:**
- Modify: `src/origin_com_automation/data_inspection.py`
- Test: `tests/unit/test_data_inspection.py`

- [ ] **Step 1: Add failing irregular-source fixtures**

Add CSV and XLSX tests containing two explanation rows, a real header, duplicate labels, decimal
comma text, scientific notation, mixed values, Unicode units, and trailing empty rows. Assert the
preview returns `header_candidates`, `selected_header_row`, `metadata_rows`, `effective_row_range`,
`preview_head`, `preview_tail`, `encoding`, `delimiter`, `decimal_convention`, `ambiguities`, and
the existing SHA-256 and column profiles.

- [ ] **Step 2: Verify the new assertions fail**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_data_inspection.py -q`

Expected: failures for missing preview and header-candidate fields.

- [ ] **Step 3: Implement bounded detection**

Decode delimited files with explicit override support and a bounded UTF-8/UTF-16/GB18030/CP1252
fallback sequence that records the selected encoding. Sniff delimiters from a bounded sample,
score the first 25 rows as header candidates, trim only fully empty leading/trailing data rows,
preserve explanation rows as metadata, and return ambiguities rather than silently selecting when
the top candidates are too close. Keep the legacy first-row behavior when the caller explicitly
passes `has_header=True` without a header-row override.

- [ ] **Step 4: Run focused and regression tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_data_inspection.py tests\unit\test_feedback_regressions.py -q`

Expected: all selected tests pass.

Commit: `git add src/origin_com_automation/data_inspection.py tests/unit/test_data_inspection.py && git commit -m "Improve offline data source preflight"`

### Task 3: Workflow planner and one-shot missing-decision report

**Files:**
- Create: `src/origin_com_automation/workflows/planner.py`
- Test: `tests/unit/test_workflow_planner.py`

- [ ] **Step 1: Write failing planner tests**

Assert `compile_workflow()` performs source inspection without calling a controller, reports all
missing branch/range/derivative/model/unit decisions in one `required_decisions` list, blocks
ambiguous headers and output overwrite, returns safe defaults separately, predicts workbook,
formula, operation, graph, manifest, and file objects, and binds the result to the spec digest.

- [ ] **Step 2: Verify planner tests fail**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_workflow_planner.py -q`

Expected: module import failure.

- [ ] **Step 3: Implement deterministic planning**

Create frozen `WorkflowPlan` and `PlannedStage` records. Resolve only deterministic metadata,
classify every scientific field as `provided`, `derived`, `required`, or `safe_default`, validate
capabilities against `capability_report()`, assign per-step idempotency keys from the plan digest
and normalized target, and return `executor_executable=False` whenever required decisions or
blockers remain.

- [ ] **Step 4: Run tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_workflow_planner.py tests\unit\test_capabilities.py -q`

Expected: all selected tests pass.

Commit: `git add src/origin_com_automation/workflows/planner.py tests/unit/test_workflow_planner.py && git commit -m "Add offline workflow planner"`

### Task 4: Structured and rebindable Origin object references

**Files:**
- Create: `src/origin_com_automation/objects/references.py`
- Modify: `src/origin_com_automation/objects/__init__.py`
- Test: `tests/unit/test_object_references.py`

- [ ] **Step 1: Write failing registry tests**

Assert an `ObjectRefRegistry` registers a workbook, worksheet, graph, and operation under logical
IDs; resolves current internal names; keeps old aliases after rename; rejects cross-session refs;
returns ambiguity instead of guessing between two fingerprint matches; and serializes refs without
COM proxy objects.

- [ ] **Step 2: Verify tests fail**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_object_references.py -q`

Expected: module import failure.

- [ ] **Step 3: Implement ObjectRef and registry**

Use strict immutable `ObjectRef` values with kind, session ID, logical ID, internal name,
container logical ID, long name, folder path, aliases, generation, stability, and verification
state. Implement register, rename, resolve, rebind, export, and import operations under a lock.

- [ ] **Step 4: Run tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_object_references.py tests\unit\test_object_plans.py -q`

Expected: all selected tests pass.

Commit: `git add src/origin_com_automation/objects/references.py tests/unit/test_object_references.py && git commit -m "Add structured Origin object references"`

### Task 5: Idempotent task ledger and fail-fast batch behavior

**Files:**
- Modify: `src/origin_com_automation/workflows/tasks.py`
- Modify: `src/origin_com_automation/workflows/batch.py`
- Test: `tests/unit/test_task_manager.py`
- Test: `tests/unit/test_batch_workflow.py`

- [ ] **Step 1: Add failing idempotency and stage tests**

Assert duplicate submission with the same idempotency key returns the original task ID, a
different function cannot reuse an active key, stage records contain expected/actual/object/error
fields, completed mutation keys cannot run twice, and batch defaults to fail-fast without creating
output directories for unstarted items.

- [ ] **Step 2: Verify failures**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_task_manager.py tests\unit\test_batch_workflow.py -q`

Expected: failures for missing idempotency and ledger behavior.

- [ ] **Step 3: Extend TaskManager and batch executor**

Add optional `idempotency_key` to `submit()`, immutable stage-event snapshots, explicit
`complete_stage()` and `fail_stage()` methods, and a completed-mutation-key set. Change batch
default from an open `on_error` string to `fail_fast=True` while accepting the legacy option for
compatibility. Create an item output directory immediately before that item starts, never during
planning.

- [ ] **Step 4: Run tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_task_manager.py tests\unit\test_batch_workflow.py -q`

Expected: all selected tests pass.

Commit: `git add src/origin_com_automation/workflows/tasks.py src/origin_com_automation/workflows/batch.py tests/unit/test_task_manager.py tests/unit/test_batch_workflow.py && git commit -m "Add idempotent fail-fast task ledger"`

### Task 6: Native expression selection and formula compatibility

**Files:**
- Create: `src/origin_com_automation/native/expressions.py`
- Modify: `src/origin_com_automation/native/xfunctions.py`
- Modify: `src/origin_com_automation/native/formulas.py`
- Test: `tests/unit/test_native_expressions.py`

- [ ] **Step 1: Write failing expression-planner tests**

Assert native scalar functions are preferred over expanded arithmetic, an explicit
`dderivative` request compiles only when the installed-version registry marks its exact contract
verified, compatible derivative Analysis Operations select `differentiate`, an incompatible
boundary or point-placement method returns a required decision, Python is never selected without
`external_explicit`, and suggested compatibility rewrites are not applied automatically.

- [ ] **Step 2: Verify tests fail**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_native_expressions.py -q`

Expected: module import failure.

- [ ] **Step 3: Implement the versioned expression registry**

Define `NativeExpressionCapability`, `FormulaDiagnostic`, and `ExpressionPlan`. Map each verified
function or X-Function to exact inputs, outputs, semantics, Origin versions, recalculation support,
and status. Add static checks for delimiters, parentheses, range syntax, common function-name
differences, dynamic indexes, and obvious numeric-domain hazards. Extend
`NATIVE_ANALYSIS_XFUNCTIONS` only for routes with matching high-level semantics and live proof.

- [ ] **Step 4: Run tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_native_expressions.py tests\unit\test_native_formulas.py tests\unit\test_native_xfunctions.py -q`

Expected: all selected tests pass.

Commit: `git add src/origin_com_automation/native/expressions.py src/origin_com_automation/native/xfunctions.py src/origin_com_automation/native/formulas.py tests/unit/test_native_expressions.py && git commit -m "Prefer verified Origin-native expressions"`

### Task 7: Selection ranges and plugin-owned helpers

**Files:**
- Create: `src/origin_com_automation/workflows/selections.py`
- Test: `tests/unit/test_workflow_selections.py`

- [ ] **Step 1: Write failing selection tests**

Assert contiguous and discontinuous ranges, forward/reverse order, category branches, explicit
filters, and missing-value rules compile into deterministic selection plans. Assert unknown branch
semantics block, helper refs use a reserved plugin prefix, and cleanup instructions cannot target a
user column.

- [ ] **Step 2: Verify tests fail**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_workflow_selections.py -q`

Expected: module import failure.

- [ ] **Step 3: Implement selection compilation**

Create immutable `SelectionPlan` and `HelperRangePlan` records. Normalize zero-based inclusive
ranges, preserve requested ordering, build exact filter predicates, and allocate helpers only in a
plugin-owned workbook/folder namespace. Include creation, verification, and cleanup stages.

- [ ] **Step 4: Run tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_workflow_selections.py -q`

Expected: all selected tests pass.

Commit: `git add src/origin_com_automation/workflows/selections.py tests/unit/test_workflow_selections.py && git commit -m "Add explicit workflow selection plans"`

### Task 8: Shared workflow executor, checkpoints, and resume

**Files:**
- Create: `src/origin_com_automation/workflows/engine.py`
- Modify: `src/origin_com_automation/workflows/executor.py`
- Test: `tests/unit/test_workflow_engine.py`

- [ ] **Step 1: Write failing fake-controller tests**

Assert execution rejects digest drift and unresolved decisions, calls existing controller methods
in the planned order, verifies each mutation before continuing, saves checkpoints after configured
phases, records stable refs and actual values, shuts down owned sessions, and resumes from the
first incomplete stage without replaying completed idempotency keys.

- [ ] **Step 2: Verify tests fail**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_workflow_engine.py -q`

Expected: module import failure.

- [ ] **Step 3: Implement execution over public controller methods**

Implement `WorkflowEngine.plan()`, `submit()`, `execute()`, `status()`, and `resume()`. Keep the
controller calls in adapters, not server code. Store the ledger as atomic JSON beside plugin-owned
checkpoint OPJU files. A resume verifies plan digest, source hashes, checkpoint hash, and previous
stage outputs before opening the checkpoint and continuing.

- [ ] **Step 4: Adapt FigureSpec without behavior drift**

Route FigureSpec stage execution through shared stage and error helpers while keeping its public
schema, digest, source defaults, native analysis defaults, and result fields unchanged.

- [ ] **Step 5: Run tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_workflow_engine.py tests\unit\test_figurespec.py tests\unit\test_task_manager.py -q`

Expected: all selected tests pass.

Commit: `git add src/origin_com_automation/workflows/engine.py src/origin_com_automation/workflows/executor.py tests/unit/test_workflow_engine.py && git commit -m "Add resumable workflow execution engine"`

### Task 9: Targeted audits, graph layout QA, and manifests

**Files:**
- Create: `src/origin_com_automation/workflows/audit.py`
- Create: `src/origin_com_automation/workflows/manifest.py`
- Modify: `src/origin_com_automation/graphs/layout.py`
- Modify: `src/origin_com_automation/graphs/preview.py`
- Test: `tests/unit/test_workflow_audit.py`
- Test: `tests/unit/test_graph_layouts.py`
- Test: `tests/unit/test_graph_preview.py`

- [ ] **Step 1: Write failing audit and layout tests**

Assert bounded audit requests reject whole-project wildcards, validate worksheet profiles,
connectors, formulas, operations, graph bindings, axes, files, and shutdown ownership, and classify
checks as verified/warning/unverified/failed. Assert layout planning reacts to curve count and label
length, and PNG QA reports content touching an edge, extreme whitespace, and suspected clipping.

- [ ] **Step 2: Verify tests fail**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_workflow_audit.py tests\unit\test_graph_layouts.py tests\unit\test_graph_preview.py -q`

Expected: failures for missing workflow audit and new QA fields.

- [ ] **Step 3: Implement audits, layout policy, and manifest rendering**

Create strict audit target/check records and adapters to existing read APIs. Add deterministic
legend columns, tick-density, palette, marker, font, and margin recommendations without applying
unverified Origin codes. Extend PNG inspection with configurable edge and whitespace thresholds.
Render a redacted canonical manifest dictionary and JSON/text artifacts; Notes creation remains a
controller adapter so tests do not require Origin.

- [ ] **Step 4: Run tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_workflow_audit.py tests\unit\test_graph_layouts.py tests\unit\test_graph_preview.py -q`

Expected: all selected tests pass.

Commit: `git add src/origin_com_automation/workflows/audit.py src/origin_com_automation/workflows/manifest.py src/origin_com_automation/graphs/layout.py src/origin_com_automation/graphs/preview.py tests/unit/test_workflow_audit.py tests/unit/test_graph_layouts.py tests/unit/test_graph_preview.py && git commit -m "Add targeted workflow audits and manifests"`

### Task 10: MCP high-level tools and transport schemas

**Files:**
- Modify: `src/origin_com_automation/server.py`
- Modify: `src/origin_com_automation/capabilities.py`
- Test: `tests/unit/test_server_tools.py`
- Test: `tests/unit/test_mcp_transport.py`

- [ ] **Step 1: Add failing tool-surface tests**

Assert the server exposes `origin_plan_workflow`, `origin_execute_workflow`,
`origin_workflow_status`, `origin_resume_workflow`, `origin_audit_result`, and
`origin_export_manifest`; schemas inline all WorkflowSpec references and enums; planning does not
activate COM; execution requires both plan digest and idempotency key; and all tools return the
standard ResultEnvelope.

- [ ] **Step 2: Verify failures**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_server_tools.py tests\unit\test_mcp_transport.py -q`

Expected: failures for missing tool names.

- [ ] **Step 3: Register thin MCP adapters**

Instantiate one WorkflowEngine beside the existing TaskManager. Keep all logic in workflow
modules, inline local schema refs for the six structured tools, translate plan/engine exceptions to
stable error codes, and add capability entries with honest verified or supported-unverified status.

- [ ] **Step 4: Run tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_server_tools.py tests\unit\test_mcp_transport.py tests\unit\test_capabilities.py -q`

Expected: all selected tests pass.

Commit: `git add src/origin_com_automation/server.py src/origin_com_automation/capabilities.py tests/unit/test_server_tools.py tests/unit/test_mcp_transport.py && git commit -m "Expose intent-aware workflow MCP tools"`

### Task 11: Skill, bilingual documentation, and complete changelog

**Files:**
- Create: `CHANGELOG.md`
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `skills/origin-automation/SKILL.md`
- Modify: `docs/REFERENCES.md`
- Test: `tests/unit/test_readme_content.py`
- Test: `tests/unit/test_skill_content.py`

- [ ] **Step 1: Add failing documentation-contract tests**

Assert both READMEs describe the same 0.3.0 critical path, six high-level tools, native expression
policy, parameter contract, fail-fast/resume rules, stable-reference limits, and manifest. Assert
the Skill tells Codex to plan once, ask all required scientific questions together, execute one
approved digest, and prefer verified `dderivative`/`differentiate` routes without changing method
semantics.

- [ ] **Step 2: Verify failures**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_readme_content.py tests\unit\test_skill_content.py -q`

Expected: failures for missing 0.3.0 workflow documentation.

- [ ] **Step 3: Write release history and synchronized docs**

Create Keep-a-Changelog-style entries for 0.1.0, 0.2.0, 0.2.1, and 0.3.0 using repository tags
and validation reports. Separate Added, Changed, Safety, Validation, and Known limits. Add concise
README release summaries linking to CHANGELOG, update all tool counts and examples, and keep the
English and Chinese ordered-section contract synchronized.

- [ ] **Step 4: Run tests and commit**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_readme_content.py tests\unit\test_skill_content.py -q`

Expected: all selected tests pass.

Commit: `git add CHANGELOG.md README.md README.zh-CN.md skills/origin-automation/SKILL.md docs/REFERENCES.md tests/unit/test_readme_content.py tests/unit/test_skill_content.py && git commit -m "Document 0.3.0 workflow system"`

### Task 12: Version, live verification, packaging, and local plugin update

**Files:**
- Modify: `pyproject.toml`
- Modify: `.codex-plugin/plugin.json`
- Modify: `src/origin_com_automation/__init__.py`
- Create: `docs/VALIDATION-0.3.0.md`
- Modify: `scripts/validate_distribution.py`
- Test: `tests/smoke/test_live_workflow_system.py`

- [ ] **Step 1: Add failing version and live-smoke contracts**

Assert package, runtime, and manifest versions agree at `0.3.0`; the live smoke creates only a
plugin-owned Origin instance, imports linked data, creates one native derivative or fit operation,
plots and exports, saves and reopens the OPJU, verifies the manifest and stage ledger, then exits
without changing pre-existing Origin PIDs.

- [ ] **Step 2: Verify version tests fail before the bump**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_release_audit.py tests\unit\test_distribution_validation.py -q`

Expected: the new expected 0.3.0 assertions fail while metadata remains 0.2.1.

- [ ] **Step 3: Bump all version sources and cachebuster**

Set Python package version to `0.3.0`, then use the plugin-creator cachebuster helper to assign the
installation version `0.3.0+codex.<timestamp>`. Do not hand-edit the marketplace entry.

- [ ] **Step 4: Run complete automated gates**

Run unit tests, README contract tests, Ruff, mypy, Python build, pip check, release audit,
distribution validator, plugin validator, and Skill validator. Expected: zero failures.

- [ ] **Step 5: Run bounded live Origin smoke tests**

Run only tests that create fresh exclusive plugin-owned instances. Record each supported or
unverified native expression route honestly. Never terminate or attach to the user's existing
Origin process. Expected: owned processes exit and pre-existing PIDs remain.

- [ ] **Step 6: Write validation report, reinstall locally, and verify MCP transport**

Record exact commands and results in `docs/VALIDATION-0.3.0.md`, update the local plugin through the
plugin-creator reinstall flow, and initialize the installed stdio MCP server to list tools and run
`origin_health_check`, `origin_capabilities`, and `origin_plan_workflow`.

- [ ] **Step 7: Commit the release candidate**

Commit: `git add pyproject.toml .codex-plugin/plugin.json src/origin_com_automation/__init__.py docs/VALIDATION-0.3.0.md scripts/validate_distribution.py tests/smoke/test_live_workflow_system.py && git commit -m "Release intent-aware workflow system 0.3.0"`

Do not tag or push until the user reviews the locally validated 0.3.0 candidate.
