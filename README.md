# Origin COM Automation

Personal Codex plugin for controlling OriginLab on Windows through a local Python MCP server. It keeps every COM proxy on one serialized STA thread and protects existing user-owned Origin sessions from writes and shutdown.

## Requirements

- Windows x64
- Origin 2024 or a compatible Origin COM server (verified with 10.1.0.178)
- Python 3.11+ x64
- A registered `Origin.Application`, `Origin.ApplicationCOMSI`, or `Origin.ApplicationSI` ProgID

The bootstrap creates a plugin-local `.venv`; it does not install packages into the system Python environment. It installs `pywin32`, MCP, NumPy/SciPy, OpenPyXL, Pillow, and `xlrd` for legacy `.xls` files.

## Setup

Clone or download the repository, open PowerShell in the repository root, and run:

```powershell
& '.\scripts\bootstrap.ps1'
& '.\scripts\diagnose.ps1'
```

The plugin-local `.venv` is intentionally not committed. The MCP server is launched with the relative Python executable defined in `.mcp.json`. A personal Codex marketplace normally stores its entry under `$HOME\.agents\plugins\marketplace.json`.

Install or update the cached Codex copy, then start a new Codex task so the MCP tools are reloaded:

```powershell
codex plugin add origin-com-automation@personal
```

## Session Modes

- **Owned (default):** only `Origin.Application` with `DispatchEx` fresh-instance activation is accepted. The fresh-proxy activation contract is the ownership basis; exactly one newly observed Origin PID is also required as a fail-closed audit gate before mutation or proxy `Exit` is allowed.
- **Attached:** requires an already running Origin and an explicit `Origin.ApplicationSI` or `Origin.ApplicationCOMSI` ProgID. Attached sessions are always user-owned and read-only; visibility is not changed and shutdown only releases the proxy. If any new Origin PID appears during attachment, the plugin rejects the ambiguous session and never calls `Exit` on it.
- **Exclusive:** only an explicitly attached, read-only SI/COMSI session may request `exclusive=true`. A successful `BeginSession` is reported separately from ownership, `EndSession` is called when detaching, and a missing or rejected lock fails instead of silently degrading.

SI/COMSI is never treated as owned, even when a new PID happens to appear. In a successful owned start, `observed_new_pid` is audit evidence only and `pid_binding_confirmed` is deliberately `false`: a PID set difference does not bind that PID to the returned COM proxy. The plugin never force-terminates an Origin process by PID.

## Tool Surface

The server exposes focused tools for exact control and digest-bound workflow tools for common
end-to-end jobs. Call `origin_capabilities` before using a specialized graph or analysis route;
the result distinguishes verified, supported-unverified, and unsupported behavior.

| Area | Tools |
|---|---|
| Environment and sessions | `origin_health_check`, `origin_capabilities`, `origin_start`, `origin_recover_session`, `origin_shutdown` |
| Projects and source safety | `origin_open_project`, `origin_save_project_copy`, `origin_save_and_replace_source`, `origin_close_project`, `origin_list_objects` |
| Data | `origin_inspect_data_source`, `origin_import_data`, `origin_read_worksheet`, `origin_write_worksheet`, `origin_transform_worksheet`, `origin_manage_connector` |
| Native objects | `origin_manage_matrix`, `origin_manage_image`, `origin_manage_project_folder`, `origin_manage_note` |
| Analysis | `origin_run_analysis`, `origin_run_xfunction`, `origin_list_analysis_operations`, `origin_get_analysis_operation`, `origin_recalculate_analysis`, `origin_manage_analysis_template`, `origin_execute_labtalk` |
| Graphs | `origin_graph_catalog`, `origin_create_plot`, `origin_create_graph`, `origin_configure_graph`, `origin_manage_graph_layout`, `origin_list_graph_templates`, `origin_apply_graph_template`, `origin_palette_catalog` |
| Export and visual QA | `origin_export_graph`, `origin_view_graph`, `origin_inspect_png` |
| High-level workflows | `origin_plan_figure`, `origin_execute_figure`, `origin_submit_batch`, `origin_task_status`, `origin_cancel_task` |
| Knowledge | `origin_query_knowledge` |

All tools return the common result envelope. Mutation tools require an owned session, use stable
object refs, and fail closed when readback or artifact verification is inconclusive.

## Fast Critical Path

The Skill first selects one route: environment diagnosis, read-only active-session inspection/export, existing-OPJU modification, or new-data analysis/plotting. Healthy routine tasks do not enter the diagnostic route.

The default modification path is:

1. One `origin_health_check` and one owned `origin_start`.
2. One `origin_open_project` working copy when a source OPJU is involved.
3. One initial `origin_list_objects` only when existing names, refs, structure, or bindings are needed.
4. Batched contiguous reads/imports/writes; import/write responses already contain their one internal readback result.
5. One exact analysis call and one combined `origin_configure_graph` call per final graph.
6. Targeted verification of result-defining counts, labels, bindings, axes, and artifacts.
7. A second `origin_list_objects` only when page structure or plot bindings changed.
8. One save/export attempt per requested artifact, verification, and `origin_shutdown`.

Successful calls are reused instead of repeated. Adjacent ranges are merged, multiple Y columns are passed together, and the Skill does not narrate each MCP call or ask the user to decide ordinary engineering details.

Failure handling is bounded: a stale object ref permits one refreshed audit and one corrected call; a validation mismatch permits one focused inspection and one targeted correction. If the same failure repeats, the workflow stops and reports the exact blocker. Writes, analyses, saves, exports, timeouts, and RPC failures are never blindly replayed.

For new data, use `target_mode="new_workbook"` and continue only when the returned `column_profiles` confirm the defining X/Y columns. Origin's user-level `Origin.otwu` can contain old long names, data, dimensions, formats, or connectors. The plugin bypasses it with the read-only system installation template, then applies exact dimensions, labels, and column formats after the block write. `target_mode="existing_worksheet"` is explicit and does not reset an existing OPJU worksheet.

## Analysis Engine

The structured analysis tool reads explicitly selected Origin worksheet columns and uses
NumPy/SciPy. Version 0.2 also provides structured X-Function calls with typed range/output/file
parameters and an explicit unverified-function gate. Native operations created by the plugin can
be listed, read, and recalculated through stable operation refs. The live Origin 10.1 regression
covers a recalculating `fitlr` operation; generic X-Functions and specialized analyses retain
their per-function capability status.

The plugin never silently changes fit method, branch, range, smoothing window, polynomial degree,
derivative order, missing-value policy, or normalization rule.

Analysis selection is explicit: `row_start` and `row_end` are inclusive 0-based worksheet rows, `filters` are AND-combined comparisons on selected x/y values, and `row_order` is `as_is` or `reverse`. Use those fields to identify a sweep branch; the plugin does not infer a branch from curve shape. Derivatives support `gradient`, `forward`, `backward`, and `central`. Invalid smoothing windows are rejected instead of rounded or shortened.

Supported structured nonlinear models in v0.2 are `exponential` and `gaussian`. Unsupported models return an error instead of selecting a substitute.

Worksheet transformations require an explicit source range and destination policy. Available
plans cover sort, filter, deduplicate, missing-value fill, transpose, merge/concat, pivot/melt, and
calculated columns; each route reports dimensions and verifies the destination. Local CSV and
Excel Data Connectors can be created, inspected, refreshed, and disconnected without turning a
remote authenticated source into an implicit dependency.

## FigureSpec and Batch Workflows

`origin_plan_figure` validates a strict FigureSpec without mutation and returns a SHA-256 digest,
exact stages, blockers, warnings, resolved paths, and graph capability states. Execution requires
the same digest, so a changed scientific or destructive request cannot run under an earlier
approval. The two primary routes are:

- `data_to_project`: inspect/import CSV, TSV, or Excel into a clean workbook, analyze, plot, save,
  export, run QA, and shut down.
- `restyle_project`: open an OPJU working copy, change the requested graph route, save separately,
  export, run QA, and shut down.

`origin_submit_batch` serializes an ordered set of FigureSpecs. Task status reports stages and
progress without worksheet values. Cancellation is accepted only while queued or between safe
items; an active COM mutation is never falsely reported as cancelled.

The current FigureSpec schema intentionally stays compact. Advanced per-layer formatting,
templates, and native operation definitions remain available through the focused tools when they
are not yet represented declaratively.

`origin_configure_graph` accepts axis limits (`x_min`, `x_max`, `y_min`, `y_max`), major tick steps, linear/log10/ln/log2 scales, axis titles, legend visibility, rescaling, per-plot Origin color/line-connection indices, and a structured `data_binding` with worksheet/X/Y/label columns and plot type. Origin 2024 axis values are `linear=0`, `log10=2`, `ln=8`, and `log2=9`.

`categorical_style` maps worksheet category strings to stable per-point color, shape, fill, and size settings. Supported marker names are `circle`, `square`, `triangle_up`, `triangle_down`, `diamond`, `hexagon`, `star`, `cross`, and `x`; colors use `#RRGGBB`. A categorical legend uses Origin's native `legendcat`, explicitly passes `combine:=1` and `showall:=0/1`, can replace an existing legend idempotently, and currently exposes the verified top-right/transparent layout. `origin_create_plot.label_column` and `data_binding.label_column` keep the plot as a direct X/Y DataPlot and link labels to the requested worksheet text dataset through Origin's custom label format, without creating a helper workbook.

LabTalk has no general stdout channel. `origin_execute_labtalk` therefore captures names declared in `result_numeric_variables` with `LTVar` and names declared in `result_string_variables` with `LTStr`; valid empty strings stay empty strings. For diagnostics, pass explicit `segments` instead of one `script`; execution stops at the first rejected segment and returns its 1-based index, statement, phase, completed count, and available Origin error variables. Legacy `result_variable`/`result_variables` remain numeric-only aliases with a deprecation warning. An optional `warning_variable` is read as a string and split into response warnings.

## MCP Call Examples

```json
{"tool":"origin_start","arguments":{"visible":false,"attach":false}}
{"tool":"origin_read_worksheet","arguments":{"name":"[WSe2Benchmark]Data","r1":0,"c1":0,"r2":25,"c2":8,"data_format":"auto"}}
{"tool":"origin_import_data","arguments":{"file_path":"C:\\data\\transfer.xlsx","worksheet_name":"Transfer","sheet_name":"Data","has_header":true,"target_mode":"new_workbook"}}
{"tool":"origin_run_analysis","arguments":{"worksheet_name":"[Transfer]Sheet1","method":"derivative","x_column":"A","y_column":"B","row_start":120,"row_end":240,"row_order":"reverse","filters":[{"column":"y","operator":"gt","value":0}],"options":{"order":1,"derivative_method":"central"}}}
{"tool":"origin_create_plot","arguments":{"worksheet_name":"[Transfer]Sheet1","graph_type":"scatter","x_column":"A","y_columns":["B"],"graph_name":"TransferGraph"}}
{"tool":"origin_create_plot","arguments":{"worksheet_name":"[WSe2Benchmark]Data","graph_type":"scatter","x_column":"A","y_columns":["B"],"label_column":"C","graph_name":"Ion_vs_Lch"}}
{"tool":"origin_export_graph","arguments":{"graph_name":"[TransferGraph]1","output_path":"C:\\results\\transfer.png","export_format":"png","overwrite":"skip"}}
```

## Safety and Failure Handling

- Source OPJU files are copied before opening; same-path copies and saves are rejected.
- Every source OPJU seen in a session remains protected until shutdown, including partial/failed loads and later project switches.
- Ordinary saves never overwrite a protected source. `origin_save_and_replace_source` is the only override path: it requires `overwrite=true`, `allow_source_overwrite=true`, and the source's current `expected_source_sha256`; saves and reopens a same-directory candidate; compares project structure; rechecks the source before commit; preserves a verified backup by default; and leaves Origin on a blank project.
- Existing outputs are not replaced unless the caller explicitly chooses an overwrite policy.
- COM calls have a configurable timeout (`ORIGIN_OPERATION_TIMEOUT_S`, default 60 seconds).
- Idempotent object listing, worksheet reads, and analysis reads retry once only for known transient RPC busy/unavailable errors. Writes, analyses with side effects, saves, and exports are never replayed.
- Timed-out writes, analyses, saves, and exports are never automatically replayed.
- After the first `COM_TIMEOUT`, `origin_shutdown` fails immediately instead of waiting on the blocked worker. Call `origin_recover_session`, which retires the entire controller and provides a fresh control surface for a later `origin_start`.
- Graph exports explicitly use `skip`, `rename`, or `replace`; Origin's interactive default is never used.
- Owned operation requires both the `Origin.Application`/`DispatchEx` fresh-proxy activation contract and exactly one newly observed audit PID. The PID difference is never treated as direct proxy-PID binding.
- SI/COMSI is accepted only through explicit read-only attachment. `exclusive=true` is an attached SI/COMSI session lock, not ownership or process isolation.
- Failed activation or poisoned-session recovery reports newly observed/owned PIDs but never terminates them without independent proxy-to-PID proof. Recovery returns whether the old PID remains present and whether cleanup was confirmed.
- Shutdown queues a one-second delayed LabTalk exit only through an owned `Origin.Application` proxy, releases the COM proxy inside its STA before Origin exits, then polls the observed lifecycle PID. This avoids pywin32 releasing a dead RPC proxy. It returns `SHUTDOWN_UNCONFIRMED` if disappearance cannot be observed; this check is exit corroboration, not proof that the PID was bound to the proxy.
- Operations are globally serialized in addition to the STA COM queue. Structured logs contain a task ID, duration, Origin version, project/object identifiers, warnings, and errors, but never worksheet values.
- If the observed lifecycle PID for an owned session disappears during an RPC failure, the error becomes `ORIGIN_PROCESS_TERMINATED` and reports any matching cleanup/watchdog task names without modifying those tasks.

## Diagnostics

If activation fails with `CO_E_SERVER_EXEC_FAILURE`, first run `scripts\diagnose.ps1`. Check COM registration in both Windows registry views, Origin/Python bitness, active Origin processes, and scheduled cleanup tasks. The plugin reports a watchdog-like task but never disables or deletes it.

The health report also checks required Python packages, executable readability, temporary-directory write access, and Python/Origin bitness compatibility. RPC disconnects, server launch failures, file locks, missing paths, and permissions return distinct error codes where Windows exposes them.

The stdio server writes protocol data only to stdout; diagnostics and Python logging go to stderr.

## Tests

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -q
& '.\.venv\Scripts\python.exe' -m ruff check .
& '.\.venv\Scripts\python.exe' -m mypy
& '.\.venv\Scripts\python.exe' -m build
& '.\.venv\Scripts\python.exe' scripts\release_audit.py .
& '.\.venv\Scripts\python.exe' scripts\validate_distribution.py .
& '.\scripts\smoke_test.ps1' -Live
$env:ORIGIN_FEEDBACK_PROJECT = 'C:\path\to\WSe2-feedback.opju'
& '.\.venv\Scripts\python.exe' -m pytest -q tests\smoke\test_feedback_wse2.py
& '.\.venv\Scripts\python.exe' "$HOME\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py" .
```

Live smoke tests are separate from unit tests and use only the owned
`Origin.Application`/`DispatchEx` mode. They never attach to or close an existing user instance.
The live suite covers mixed-XLSX import/write readback, a native recalculating linear fit, Data
Connector refresh/disconnect, Matrix persistence, Image Page import, Notes and Project Folders,
graph preview pixel metrics, dual-Y command routing, a complete FigureSpec, and a two-item batch.
The feedback regression works only on a temporary OPJU copy and proves graph editability through
decoded pixel changes and restoration. A unit test also launches the actual stdio MCP server and
calls `origin_health_check` through MCP transport.

## Update And Uninstall

After editing the plugin, refresh the manifest cachebuster and reinstall it from the personal marketplace. A new Codex task is required to load the refreshed MCP server.

```powershell
& '.\.venv\Scripts\python.exe' "$HOME\.codex\skills\.system\plugin-creator\scripts\update_plugin_cachebuster.py" .
codex plugin add origin-com-automation@personal
```

To remove the installed cache and registration without deleting the source directory:

```powershell
codex plugin remove origin-com-automation@personal
```

## Verified Scope and Known Limits

- Verified on Origin 10.1.0.178: safe owned-session lifecycle, mixed Excel import/write readback,
  editable OPJU save/reopen, `fitlr` native operation recalculation, local CSV connector lifecycle,
  Matrix read/write persistence, PNG Image Page import, Notes, Project Folder create/list/rename,
  graph preview pixel metrics, FigureSpec data-to-project execution, and two-item serial batch.
- Supported-unverified: Image Page export/conversion, Matrix transformations, folder move/delete,
  analysis templates, graph-template application, and specialized 2D/3D/statistical graph
  families. These routes require explicit opt-in where schemas expose it and must not be reported
  as verified merely because Origin accepted one command.
- Origin's COM interface does not provide a direct proxy-to-PID binding. PID observations remain
  audit evidence only and are never used for force termination.
- Structured nonlinear fitting currently provides exponential and Gaussian models. The verified
  categorical legend exposes the top-right transparent layout.

See [References and Attribution](docs/REFERENCES.md) for the two public projects reviewed during
the v0.2 design and the boundary between inspiration and this independent implementation.
