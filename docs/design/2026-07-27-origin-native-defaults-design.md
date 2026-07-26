# Origin-Native Defaults Design

Status: approved direction, implementation review pending

Target: `origin-com-automation` 0.3 development

Verified baseline: Windows 11 x64, Python x64, Origin 10.1.0.178

## 1. Goal

Origin projects produced by the plugin should remain inspectable, editable, refreshable, and
recalculating inside Origin. Unless the caller explicitly requests a snapshot or Python backend:

- imported local files remain connected to their sources;
- derived worksheet columns retain an Origin Set Column Values `F(x)` formula;
- fits and supported analyses create Origin-native Analysis Operations;
- unsupported native work fails clearly instead of silently materializing external results.

## 2. Default Contract

### Source data

`origin_import_data` gains `source_mode="linked"|"snapshot"`, defaulting to `linked` for CSV,
TSV, XLS, XLSX, and XLSM. Linked import creates or reuses a clean target worksheet, adds the
appropriate local-file Data Connector, imports once, and verifies:

- canonical source path and source hash;
- connector type and connected state;
- refresh result;
- destination row and column counts;
- per-column non-empty, numeric, text, and missing counts;
- critical-column values when provided.

The worksheet retains Origin's cached data if the source later becomes unavailable. Refresh then
fails with a source-specific error while leaving the last confirmed worksheet values intact.

`source_mode="snapshot"` preserves the existing verified mixed-data import path. Importing into an
existing worksheet remains explicit and never resets an existing OPJU page implicitly.

### Column formulas

A new `origin_set_column_formula` tool accepts a stable worksheet ref, target column, exact Origin
formula, optional Before Formula Script, row bounds, and `recalculate_mode="auto"|"manual"|"none"`.
The default is `auto`. It uses Origin Set Column Values rather than calculating values in Python.

Success requires readback of the stored formula, stored script, recalculation mode, target range,
and representative output values. A non-throwing LabTalk command alone is insufficient.

The existing `origin_transform_worksheet(action="calculated_column")` becomes an Origin-native
formula route by default. Its simple left/operator/right form compiles to a Set Values formula.
Materialized external calculation requires an explicit `execution_mode="materialized"` option.

### Analysis and fitting

`origin_run_analysis` defaults to:

- `backend="origin_native"`;
- `create_operation=true`;
- `recalculate_mode="auto"`.

The controller maps supported methods to validated X-Functions and exact parameter schemas.
Linear fitting uses `fitlr`; additional methods are enabled only after their installed Origin
syntax, output ranges, operation registration, and recalculation behavior are verified. Each
successful native analysis returns the X-Function, normalized parameters, stable operation ref,
input refs, output refs, report/output worksheet refs, recalculation mode, and state.

When a requested method has no verified native route, the tool returns
`ORIGIN_NATIVE_METHOD_UNAVAILABLE` with the exact supported alternatives. It never silently calls
NumPy or SciPy. Python analysis remains available only through explicit `backend="python"`, and
its result contains `editable_in_origin=false` and a warning that no native operation was created.

### High-level workflows

FigureSpec gains explicit `source_mode`, analysis `backend`, `create_operation`, and
`recalculate_mode` fields with the same native-first defaults. The plan reports connector and
native-operation stages before mutation. Execution stops if a required source link, formula
readback, or operation registration cannot be confirmed.

## 3. Compatibility

- Existing callers that explicitly pass `backend="python"` or `source_mode="snapshot"` keep the
  previous behavior.
- The public tool names and common result envelope remain stable.
- A default behavior change is intentional and documented as a minor-version workflow change.
- Attached SI/COMSI sessions remain read-only; all connectors, formulas, and operations require an
  owned session.
- Existing OPJU modification does not reconnect or replace worksheets unless explicitly asked.

## 4. Failure Handling

- Missing or locked source: return `DATA_SOURCE_UNAVAILABLE` or `DATA_SOURCE_LOCKED`; preserve
  cached data and do not disconnect automatically.
- Connector import mismatch: return `CONNECTOR_IMPORT_UNCONFIRMED` with source and destination
  profiles; stop before analysis.
- Formula rejection/readback mismatch: return `COLUMN_FORMULA_UNCONFIRMED`; do not replace it with
  static values.
- Unsupported native method: return `ORIGIN_NATIVE_METHOD_UNAVAILABLE`; do not fall back.
- Operation registration or recalculation mismatch: return
  `ANALYSIS_OPERATION_UNCONFIRMED` or `RECALCULATION_UNCONFIRMED`; do not replay the mutation.
- COM timeout follows the existing poisoned-session recovery path and never retries a mutation.

## 5. Implementation Boundaries

- Extend connector planning and controller orchestration instead of duplicating connector logic
  inside the server layer.
- Add a bounded native column-formula module for escaping, command construction, and readback.
- Extend the existing X-Function registry one verified analysis family at a time.
- Keep Python analysis implementation available as an explicit compatibility backend.
- Update the Origin Skill so source linking and native operations are part of the shortest normal
  route, not optional diagnostic work.

## 6. Test Plan

### Unit and MCP transport

- Import schema defaults to `source_mode="linked"`; explicit snapshot remains accepted.
- Analysis schema defaults to native backend, operation creation, and auto recalculation.
- No-native-route tests prove there is no Python fallback.
- Formula builder rejects unsafe refs/scripts, preserves valid Origin expressions, and validates
  readback.
- FigureSpec digest changes when source or analysis execution mode changes.
- MCP schemas expose all enums and defaults.

### Live Origin 10.1

1. Connect a CSV, verify values, edit the CSV, refresh, and verify changed worksheet values.
2. Save and reopen OPJU, confirm connector source and cached data remain present.
3. Set a column `F(x)` formula, verify displayed values, edit an input cell, and confirm automatic
   recalculation before and after OPJU reopen.
4. Create a native linear fit, change input data, confirm Analysis Operation recalculation, and
   verify report/output persistence after reopen.
5. Run an unsupported native method and prove no external result columns are created.
6. Confirm every owned test instance exits while a pre-existing user Origin process remains.

## 7. Acceptance Criteria

- The default new-data workflow returns `source_mode="linked"`, a verified connector ref, and a
  native operation ref for supported analysis.
- Origin visibly retains the source connection, column formula, and analysis operation after save
  and reopen.
- Modifying source or input data updates outputs through Origin refresh/recalculation.
- Python work occurs only after an explicit caller choice and is labeled non-native.
- All existing safety, mixed-data integrity, timeout recovery, packaging, and release tests pass.
