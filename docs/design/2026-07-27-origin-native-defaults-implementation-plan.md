# Origin-Native Defaults Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make linked source data, Origin column formulas, and Origin-native Analysis Operations
the normal editable workflow while retaining explicit snapshot and Python compatibility modes.

**Architecture:** Extend the existing strict MCP schemas and controller orchestration rather than
creating a parallel server. Connector lifecycle remains in `objects/connectors.py`; a new bounded
native formula module builds and validates Set Column Values commands; the X-Function registry
remains the only native analysis allowlist. FigureSpec propagates the same defaults end to end.

**Tech Stack:** Python 3.11+, Pydantic, FastMCP, pywin32 COM, LabTalk, Origin X-Functions, pytest.

---

### Task 1: Lock Public Defaults and Compatibility Modes

**Files:**
- Modify: `src/origin_com_automation/server.py`
- Modify: `src/origin_com_automation/services/analysis.py`
- Test: `tests/unit/test_server_tools.py`
- Test: `tests/unit/test_analysis_engine.py`

- [ ] **Step 1: Write failing schema tests**

Add assertions that `origin_import_data.source_mode` defaults to `linked` and exposes
`linked|snapshot`; `origin_run_analysis.options.backend` defaults to `origin_native`,
`create_operation` defaults to true, and `recalculate_mode` defaults to `auto`.

```python
assert import_schema["source_mode"]["default"] == "linked"
assert set(import_schema["source_mode"]["enum"]) == {"linked", "snapshot"}
assert analysis_options["backend"]["default"] == "origin_native"
assert analysis_options["create_operation"]["default"] is True
assert analysis_options["recalculate_mode"]["default"] == "auto"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_server_tools.py tests\unit\test_analysis_engine.py -q
```

Expected: failures showing the current static import and Python analysis defaults.

- [ ] **Step 3: Implement strict defaults**

Add `source_mode: Literal["linked", "snapshot"] = "linked"` to `origin_import_data` and forward it
to the controller. Change the Pydantic analysis defaults to:

```python
backend: Literal["python", "origin_native"] = "origin_native"
create_operation: bool = True
recalculate_mode: Literal["none", "manual", "auto"] = "auto"
```

Keep explicit Python calls valid. Make `run_analysis_data` default its internal marker to Python
only because that function is the explicit Python engine, not the public policy surface.

- [ ] **Step 4: Run targeted tests and verify GREEN**

Run the same command and require all tests to pass.

- [ ] **Step 5: Commit**

```powershell
git add src/origin_com_automation/server.py src/origin_com_automation/services/analysis.py tests/unit/test_server_tools.py tests/unit/test_analysis_engine.py
git commit -m "Default public workflows to Origin-native execution"
```

### Task 2: Make New-Data Import Source-Linked

**Files:**
- Modify: `src/origin_com_automation/objects/connectors.py`
- Modify: `src/origin_com_automation/com/origin_api.py`
- Test: `tests/unit/test_object_plans.py`
- Test: `tests/unit/test_object_controllers.py`
- Test: `tests/unit/test_feedback_regressions.py`

- [ ] **Step 1: Write failing linked-import tests**

Cover CSV and Excel connector selection, canonical source path, source hash, returned connector ref,
column profiles, and explicit snapshot bypass. The controller test must assert that a linked import
calls connector creation/refresh after creating the clean target and does not execute the static
block-write branch.

```python
result = controller.import_data(file_path=str(source), source_mode="linked")
assert result.data["source_mode"] == "linked"
assert result.data["connector"]["connected"] is True
assert result.data["connector"]["source_sha256"] == sha256(source.read_bytes()).hexdigest()
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_object_plans.py tests\unit\test_object_controllers.py tests\unit\test_feedback_regressions.py -q
```

Expected: `source_mode` is unknown and linked metadata is absent.

- [ ] **Step 3: Implement linked import orchestration**

In `import_data`, validate `source_mode`; route snapshot to the existing verified mixed-data path.
For linked mode:

1. validate and profile the source before COM mutation;
2. create a clean workbook/worksheet through the system template path;
3. add the local CSV or Excel connector with `DC.Allow`, `wbook.dc.add`, `DC.Source`, and
   `DC.Import` through the existing connector helpers;
4. resolve and return the actual worksheet ref because Origin may rename it;
5. profile destination columns and compare critical non-empty counts;
6. return source path, SHA-256, connector type/ref/state, refresh verification, and cached-data
   state.

Do not disconnect after import. On refresh failure, return a source-specific error without clearing
the worksheet.

- [ ] **Step 4: Verify GREEN and snapshot compatibility**

Run the targeted command and the existing mixed-import tests. Require both linked and snapshot
paths to pass.

- [ ] **Step 5: Commit**

```powershell
git add src/origin_com_automation/objects/connectors.py src/origin_com_automation/com/origin_api.py tests/unit/test_object_plans.py tests/unit/test_object_controllers.py tests/unit/test_feedback_regressions.py
git commit -m "Link imported data to local source files by default"
```

### Task 3: Add Origin Set Column Values Formula Tool

**Files:**
- Create: `src/origin_com_automation/native/formulas.py`
- Modify: `src/origin_com_automation/com/origin_api.py`
- Modify: `src/origin_com_automation/server.py`
- Modify: `src/origin_com_automation/objects/worksheets.py`
- Test: `tests/unit/test_native_formulas.py`
- Test: `tests/unit/test_server_tools.py`
- Test: `tests/unit/test_worksheet_transforms.py`

- [ ] **Step 1: Write failing formula-plan tests**

Test stable worksheet/column refs, exact formula retention, optional Before Formula Script, row
bounds, auto/manual/none modes, LabTalk escaping, and rejection of empty formulas or unsafe refs.

```python
plan = build_column_formula_plan(
    worksheet_ref="[Book1]Data",
    column="C",
    formula="col(A)*col(B)",
    before_script="double scale=1;",
    recalculate_mode="auto",
)
assert plan.formula == "col(A)*col(B)"
assert plan.command.startswith("wks.col3.SetFormula(")
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_native_formulas.py tests\unit\test_server_tools.py tests\unit\test_worksheet_transforms.py -q
```

Expected: missing module/tool and materialized calculated-column behavior.

- [ ] **Step 3: Implement formula planning and COM execution**

Create immutable `ColumnFormulaPlan` plus builders for safe Origin references and quoted formula
strings. Add `OriginController.set_column_formula` that activates the stable worksheet, stores the
formula/script/recalculation setting using the verified Origin COM/LabTalk path, recalculates once,
then reads back formula metadata and representative values. Return `COLUMN_FORMULA_UNCONFIRMED`
on any mismatch.

Expose `origin_set_column_formula` with explicit JSON schema fields. Change
`calculated_column` to compile left/operator/right into this native formula route by default;
require `execution_mode="materialized"` for the old data-copy behavior.

- [ ] **Step 4: Verify GREEN**

Run targeted tests and inspect the MCP schema to ensure formula, script, range, and recalculation
enums are discoverable.

- [ ] **Step 5: Commit**

```powershell
git add src/origin_com_automation/native/formulas.py src/origin_com_automation/com/origin_api.py src/origin_com_automation/server.py src/origin_com_automation/objects/worksheets.py tests/unit/test_native_formulas.py tests/unit/test_server_tools.py tests/unit/test_worksheet_transforms.py
git commit -m "Preserve derived columns as Origin formulas"
```

### Task 4: Enforce Native Analysis Without Silent Fallback

**Files:**
- Modify: `src/origin_com_automation/native/xfunctions.py`
- Modify: `src/origin_com_automation/native/operations.py`
- Modify: `src/origin_com_automation/com/origin_api.py`
- Test: `tests/unit/test_native_xfunctions.py`
- Test: `tests/unit/test_native_operations.py`
- Test: `tests/unit/test_safety_reliability_regressions.py`

- [ ] **Step 1: Write failing native-default and no-fallback tests**

Assert that a default linear fit invokes `fitlr -r 2` for auto recalculation and returns an
operation ref. Assert that an unsupported native method returns
`ORIGIN_NATIVE_METHOD_UNAVAILABLE`, does not call `run_analysis_data`, and does not write result
columns. Assert explicit `backend="python"` still works and returns `editable_in_origin=false`.

- [ ] **Step 2: Verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_native_xfunctions.py tests\unit\test_native_operations.py tests\unit\test_safety_reliability_regressions.py -q
```

Expected: current default uses Python and operation mode is not auto.

- [ ] **Step 3: Implement native routing and explicit fallback labels**

Normalize absent options to the public native defaults. Map only registry-verified methods. For an
unmapped method, fail with the verified method list. Never enter `run_analysis_data` from a native
request. For Python requests, add:

```python
{
    "backend": "python",
    "editable_in_origin": False,
    "native_operation_created": False,
}
```

and a warning explaining that Origin has no recalculating operation for that result.

- [ ] **Step 4: Verify GREEN**

Run targeted tests and confirm the generated `fitlr` command, operation registry, and no-fallback
spy assertions.

- [ ] **Step 5: Commit**

```powershell
git add src/origin_com_automation/native/xfunctions.py src/origin_com_automation/native/operations.py src/origin_com_automation/com/origin_api.py tests/unit/test_native_xfunctions.py tests/unit/test_native_operations.py tests/unit/test_safety_reliability_regressions.py
git commit -m "Require explicit opt-in for external analysis"
```

### Task 5: Propagate Defaults Through FigureSpec

**Files:**
- Modify: `src/origin_com_automation/workflows/figurespec.py`
- Modify: `src/origin_com_automation/workflows/executor.py`
- Test: `tests/unit/test_figurespec.py`
- Test: `tests/unit/test_batch_workflow.py`

- [ ] **Step 1: Write failing FigureSpec tests**

Assert default linked input and native/auto analyses, digest sensitivity to execution modes, plan
stages for connector and native operation, and forwarding into controller calls.

- [ ] **Step 2: Verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_figurespec.py tests\unit\test_batch_workflow.py -q
```

- [ ] **Step 3: Implement model and executor propagation**

Add `FigureInput.source_mode` and explicit analysis backend/operation/recalculation fields. Include
them in the strict digest naturally through Pydantic serialization. Compile connector and native
operation stages. Forward source mode to import and native settings to analysis.

- [ ] **Step 4: Verify GREEN and commit**

```powershell
git add src/origin_com_automation/workflows/figurespec.py src/origin_com_automation/workflows/executor.py tests/unit/test_figurespec.py tests/unit/test_batch_workflow.py
git commit -m "Carry Origin-native defaults through FigureSpec"
```

### Task 6: Update Skill, Documentation, and Capability Metadata

**Files:**
- Modify: `skills/origin-automation/SKILL.md`
- Modify: `README.md`
- Modify: `src/origin_com_automation/capabilities.py`
- Modify: `src/origin_com_automation/resources/knowledge.json`
- Test: `tests/unit/test_skill_content.py`
- Test: `tests/unit/test_capabilities.py`
- Test: `tests/unit/test_knowledge.py`

- [ ] **Step 1: Add failing content tests**

Require the Skill to state linked-source default, Origin-native default, explicit snapshot/Python
opt-in, `F(x)` formula preservation, and prohibition on silent fallback.

- [ ] **Step 2: Verify RED, update content, verify GREEN**

Update concise critical paths and examples. Capability metadata distinguishes verified native
linear fit/formula/connector routes from supported-unverified families. Run the three targeted test
files and both official validators.

- [ ] **Step 3: Commit**

```powershell
git add skills/origin-automation/SKILL.md README.md src/origin_com_automation/capabilities.py src/origin_com_automation/resources/knowledge.json tests/unit/test_skill_content.py tests/unit/test_capabilities.py tests/unit/test_knowledge.py
git commit -m "Document editable Origin-native workflow defaults"
```

### Task 7: Live Origin Verification and Local Plugin Release

**Files:**
- Create: `tests/smoke/test_live_native_defaults.py`
- Create: `docs/VALIDATION-0.3.0.md`
- Modify: `.codex-plugin/plugin.json` to version 0.3.0 plus a Codex cachebuster
- Modify: `pyproject.toml` to version 0.3.0
- Modify: `src/origin_com_automation/__init__.py` to version 0.3.0

- [ ] **Step 1: Add live smoke covering connector, formula, and fit persistence**

The test creates a temporary CSV, imports it with the default linked mode, edits and refreshes the
source, adds `col(C)=col(A)*col(B)` as an auto formula, changes an input, creates a native linear
fit, saves/reopens OPJU, and verifies the connector, formula, values, operation, and output refs.
It also proves an unsupported native request creates no result objects and preserves any
pre-existing Origin PID.

- [ ] **Step 2: Run complete local gates**

```powershell
.\.venv\Scripts\python.exe -m compileall -q src tests
.\.venv\Scripts\python.exe -m pytest tests\unit -q -p no:faulthandler
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m build
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts\release_audit.py .
```

Require zero failures.

- [ ] **Step 3: Run live Origin smoke**

```powershell
$env:ORIGIN_LIVE_SMOKE='1'
$env:ORIGIN_ALLOW_EXISTING='1'
.\.venv\Scripts\python.exe -m pytest tests\smoke\test_live_native_defaults.py -q -p no:faulthandler
```

Require linked refresh, formula recalculation, native fit recalculation, persistence, and owned
shutdown to pass. Re-run existing mixed-data, native analysis, objects, graph, FigureSpec batch,
and WSe2 feedback smoke tests.

- [ ] **Step 4: Refresh and verify the installed plugin**

Use the plugin-creator cachebuster helper, reinstall from the personal marketplace, initialize the
installed stdio MCP server, list tools, and call health/capabilities. Start a new Codex task only
after installation.

- [ ] **Step 5: Commit without pushing**

Commit the implementation and validation report on the feature branch. Confirm a clean worktree,
the installed version, and that only the user's pre-existing Origin PID remains. Do not push until
the user reviews the local result.
