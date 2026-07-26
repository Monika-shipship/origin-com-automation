# Origin COM Automation

Personal Codex plugin for controlling OriginLab on Windows through a local Python MCP server. It keeps every COM proxy on one serialized STA thread and protects existing user-owned Origin sessions from writes and shutdown.

## Requirements

- Windows x64
- Origin 2024 or a compatible Origin COM server (verified with 10.1.0.178)
- Python 3.11+ x64
- A registered `Origin.Application`, `Origin.ApplicationCOMSI`, or `Origin.ApplicationSI` ProgID

The bootstrap creates a plugin-local `.venv`; it does not install packages into the system Python environment. It installs `pywin32`, MCP, NumPy/SciPy, OpenPyXL, and `xlrd` for legacy `.xls` files.

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

## Tools

| Tool | Purpose |
|---|---|
| `origin_health_check` | Inspect Python, Origin binary, COM registration, and active process count without activation |
| `origin_start` | Start an owned hidden instance or explicitly attach read-only |
| `origin_open_project` | Copy an OPJU and open only the working copy |
| `origin_save_project_copy` | Wait for pending recalculation, save separately, and validate the file |
| `origin_save_and_replace_source` | High-risk source replacement through a saved/reopened candidate, dual confirmation, authorized SHA-256, and same-directory backup |
| `origin_list_objects` | Audit pages, workbooks, worksheets, column labels, matrices, graphs, layers, and plot data sources |
| `origin_import_data` | Import CSV, TSV, XLS, XLSX, or XLSM into a clean new workbook by default; profile and verify every destination column |
| `origin_read_worksheet` / `origin_write_worksheet` | Read mixed, numeric, string, variant, or categorical-label data; every write performs an exact lightweight readback |
| `origin_run_analysis` | Run descriptive statistics, fits, smoothing, derivatives, and peak analysis |
| `origin_execute_labtalk` | Execute explicit LabTalk and read explicitly typed numeric/string LT variables |
| `origin_create_plot` / `origin_configure_graph` | Create graphs with direct X/Y/label bindings, configure axes/styles, and apply categorical markers/legends |
| `origin_export_graph` | Export PNG, TIFF, PDF, or SVG with a non-interactive overwrite policy |
| `origin_recover_session` | Abandon and replace a poisoned controller without queuing onto its blocked COM worker |
| `origin_close_project` / `origin_shutdown` | Close an owned project or safely release a healthy session |

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

The structured analysis tool reads explicitly selected Origin worksheet columns and uses NumPy/SciPy. Responses identify the method and parameters. For Origin-native X-Functions, use `origin_execute_labtalk` with a fully qualified range and a named result variable. The plugin never silently changes fit method, branch, range, smoothing window, polynomial degree, or derivative order.

Analysis selection is explicit: `row_start` and `row_end` are inclusive 0-based worksheet rows, `filters` are AND-combined comparisons on selected x/y values, and `row_order` is `as_is` or `reverse`. Use those fields to identify a sweep branch; the plugin does not infer a branch from curve shape. Derivatives support `gradient`, `forward`, `backward`, and `central`. Invalid smoothing windows are rejected instead of rounded or shortened.

Supported nonlinear models in v0.1 are `exponential` and `gaussian`. Unsupported models return an error instead of selecting a substitute.

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
& '.\scripts\smoke_test.ps1' -Live
$env:ORIGIN_FEEDBACK_PROJECT = 'C:\path\to\WSe2-feedback.opju'
& '.\.venv\Scripts\python.exe' -m pytest -q tests\smoke\test_feedback_wse2.py
& '.\.venv\Scripts\python.exe' "$HOME\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py" .
```

Live smoke tests are separate from unit tests and use only the owned `Origin.Application`/`DispatchEx` mode. They never attach to or close an existing user instance. The generic smoke imports a 26-row mixed XLSX through the system template, verifies `Ion=2260...950`, writes existing/new numeric/text/mixed columns, then plots, exports, and saves. The feedback regression works only on a temporary working copy; proves B and C independently change decoded PNG pixels; verifies each restoration returns to the original pixel baseline; reopens the saved project; and polls until the observed lifecycle PID exits. A unit test also launches the actual stdio MCP server and calls `origin_health_check` through MCP transport.

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

Known limitations: Origin's standard COM interface does not expose a direct proxy-to-PID binding, so PID observations are reported with `pid_binding_confirmed=false` and are never used for force termination. Structured nonlinear fitting currently provides exponential and Gaussian models. The structured categorical legend currently exposes the verified top-right, transparent layout. Other Origin-native X-Functions and specialized graph themes require explicit LabTalk and are reported as such rather than silently substituted.
