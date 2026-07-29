# Origin COM Automation Tool Reference

The plugin exposes 45 public tools. Codex normally chooses and calls them from a plain-language
request; this catalog is for users who want to check the exact surface or write structured calls.
Unknown arguments are rejected. Unless a tool says otherwise, results use a common envelope with
`success`, `data`, `warnings`, `error_code`, `error_message`, `artifacts`, `duration_ms`, and
`origin_version`.

## Environment And Discovery

| Tool | Purpose |
|---|---|
| `origin_health_check` | Inspect registration, executable access, Python bitness, dependencies, active processes, and relevant scheduled tasks without activating COM. |
| `origin_capabilities` | Report `verified`, `supported_unverified`, and `unsupported` capability states, optionally for one domain. |
| `origin_inspect_data_source` | Profile a CSV, TSV, or Excel source and optional sheet before starting Origin. |
| `origin_graph_catalog` | List graph families, required roles, Origin mappings, and verification status. |
| `origin_palette_catalog` | List plugin-owned scientific palettes, exact colors, and restrictions. |
| `origin_list_graph_templates` | Discover OTP/OTPU files only below explicit roots. |
| `origin_inspect_png` | Measure dimensions, alpha, nonblank bounds, and expected-color pixels in a PNG. |
| `origin_query_knowledge` | Search local capability summaries linked to official Origin documentation. |

## Sessions And Projects

| Tool | Purpose |
|---|---|
| `origin_start` | Create a plugin-owned Origin instance or explicitly attach to a running SI/COMSI session. |
| `origin_open_project` | Copy an OPJU and open the protected working copy. |
| `origin_save_project_copy` | Save the active project to a separate validated OPJU path. |
| `origin_save_and_replace_source` | Replace a protected source only after dual confirmation, expected-hash checks, candidate reopen validation, and optional backup. |
| `origin_list_objects` | List pages, layers, worksheet columns, and plot sources with reusable stable refs. |
| `origin_close_project` | Close the current project by opening a blank project; refuse unsaved changes by default. |
| `origin_recover_session` | Retire a timed-out controller and provide a fresh control surface without queueing on the blocked STA worker. |
| `origin_shutdown` | Exit only a plugin-owned instance, or detach from a user-owned session. |

## Worksheet Data And Connections

| Tool | Purpose |
|---|---|
| `origin_import_data` | Import CSV, TSV, XLS, XLSX, or XLSM with explicit header policy and linked/snapshot source mode. |
| `origin_transform_worksheet` | Sort, filter, deduplicate, fill missing values, transpose, merge, concatenate, pivot, melt, or add a calculated column into a distinct destination. |
| `origin_set_column_formula` | Set and verify an editable Origin `F(x)` formula, optional Before Formula Script, row range, and recalculation mode. |
| `origin_manage_connector` | Create, inspect, refresh, or explicitly disconnect a local CSV/Excel Data Connector. |
| `origin_read_worksheet` | Read a 0-based rectangle as auto, numeric, string, variant, or categorical-label values. |
| `origin_write_worksheet` | Write a rectangular mixed-value array and verify exact readback. |

## Native Project Objects

| Tool | Purpose |
|---|---|
| `origin_manage_matrix` | Create/read/write Matrix data or transpose, rotate, or flip it. |
| `origin_manage_image` | Create, inspect, import, export, or delete an Image Page by stable ref. |
| `origin_manage_project_folder` | List, create, move, rename, or confirmed-recursively delete a Project Explorer folder. |
| `origin_manage_note` | Inspect, create, write, export, or delete an Origin Notes page. |

## Analysis

| Tool | Purpose |
|---|---|
| `origin_run_analysis` | Analyze explicit X/Y columns, inclusive rows, AND filters, and as-is/reverse order using a requested backend. |
| `origin_run_xfunction` | Run one validated allowlisted X-Function with typed parameters and declared outputs. |
| `origin_list_analysis_operations` | List Analysis Operations created and tracked by this plugin session. |
| `origin_get_analysis_operation` | Read native state for one stable plugin-managed Analysis Operation ref. |
| `origin_recalculate_analysis` | Recalculate one plugin-managed native Analysis Operation without retrying mutation. |
| `origin_manage_analysis_template` | Save or load an explicit Origin Analysis Template with path and overwrite checks. |
| `origin_execute_labtalk` | Execute an explicit LabTalk script or ordered segments and identify the failing segment. |

## Graphs And Export

| Tool | Purpose |
|---|---|
| `origin_create_plot` | Create a typed graph from one X column, one or more Y columns, and an optional label column. |
| `origin_create_graph` | Create a catalog graph from explicit named roles; unverified graph types require opt-in. |
| `origin_manage_graph_layout` | Add layers, build grids/insets/dual-Y layouts, link axes, merge graphs, or extract layers. |
| `origin_apply_graph_template` | Apply one digest-locked graph template after layer compatibility checks. |
| `origin_view_graph` | Export a temporary preview and return the PNG plus pixel QA metrics. |
| `origin_configure_graph` | Configure axes, data binding, categorical markers, legends, and supported styling in one pass. |
| `origin_export_graph` | Export a named graph with an explicit `skip`, `rename`, or `replace` policy and validate the artifact. |

## Planned And Batch Workflows

| Tool | Purpose |
|---|---|
| `origin_plan_figure` | Preflight a strict FigureSpec without mutation and return its immutable execution digest. |
| `origin_execute_figure` | Queue one FigureSpec only when it still matches its approved digest. |
| `origin_submit_batch` | Queue multiple approved FigureSpecs for one-at-a-time execution with stop/continue error policy. |
| `origin_task_status` | Read queued, running, or terminal workflow state and completed stages. |
| `origin_cancel_task` | Cancel only pending work; never interrupt an active Origin mutation. |

## Structured Call Examples

These examples show the call shape. Paths, object refs, columns, ranges, methods, and output policy
must match the real task.

### Diagnose and start an owned background session

```json
{"tool":"origin_health_check","arguments":{}}
{"tool":"origin_start","arguments":{"visible":false,"attach":false}}
```

### Inspect and import linked Excel data

```json
{"tool":"origin_inspect_data_source","arguments":{"file_path":"C:\\data\\transfer.xlsx","sheet_name":"Data","has_header":true}}
{"tool":"origin_import_data","arguments":{"file_path":"C:\\data\\transfer.xlsx","worksheet_name":"Transfer","sheet_name":"Data","has_header":true,"target_mode":"new_workbook","source_mode":"linked"}}
```

Use `"source_mode":"snapshot"` only for a disconnected copy. Refresh a linked source explicitly:

```json
{"tool":"origin_manage_connector","arguments":{"action":"refresh","worksheet_ref":"[Transfer]Sheet1"}}
```

### Create an editable Origin formula

```json
{"tool":"origin_set_column_formula","arguments":{"worksheet_ref":"[Transfer]Sheet1","column":"C","formula":"col(A)*col(B)","row_start":0,"row_end":-1,"recalculate_mode":"auto"}}
```

### Run and inspect a native linear fit

```json
{"tool":"origin_run_analysis","arguments":{"worksheet_name":"[Transfer]Sheet1","method":"linear_fit","x_column":"A","y_column":"B","row_start":0,"row_end":-1,"row_order":"as_is","options":{"backend":"origin_native","create_operation":true,"recalculate_mode":"auto"}}}
{"tool":"origin_get_analysis_operation","arguments":{"operation_ref":"operation-ref-returned-by-the-fit"}}
```

The second call must use the real stable ref returned by the first call. Do not invent it.

### Explicit Python compatibility analysis

```json
{"tool":"origin_run_analysis","arguments":{"worksheet_name":"[Transfer]Sheet1","method":"derivative","x_column":"A","y_column":"B","row_start":120,"row_end":240,"row_order":"reverse","filters":[{"column":"y","operator":"gt","value":0}],"options":{"backend":"python","order":1,"derivative_method":"central","create_operation":false,"recalculate_mode":"none"}}}
```

This route is intentionally labeled as not creating an editable native Analysis Operation.

### Create, style, preview, and export a multi-series plot

```json
{"tool":"origin_create_plot","arguments":{"worksheet_name":"[Transfer]Sheet1","graph_type":"line_symbol","x_column":"A","y_columns":["B","C","D"],"graph_name":"TransferGraph"}}
{"tool":"origin_configure_graph","arguments":{"graph_name":"[TransferGraph]1","options":{"legend":true,"x_title":"Gate voltage (V)","y_title":"Drain current (A)"}}}
{"tool":"origin_view_graph","arguments":{"graph_name":"[TransferGraph]1"}}
{"tool":"origin_export_graph","arguments":{"graph_name":"[TransferGraph]1","output_path":"C:\\results\\transfer.png","export_format":"png","overwrite":"skip"}}
```

Graph option schemas are strict and can evolve; let Codex inspect the current tool schema rather
than adding guessed fields.

### Save without overwriting the source

```json
{"tool":"origin_save_project_copy","arguments":{"target_path":"C:\\results\\transfer.opju","overwrite":false}}
{"tool":"origin_shutdown","arguments":{}}
```

### Recover after a timeout

```json
{"tool":"origin_recover_session","arguments":{}}
{"tool":"origin_start","arguments":{"visible":false,"attach":false}}
```

Recovery creates a new controller. It does not assert that the timed-out mutation completed and
does not blindly replay it.

## Safety Notes

- Mutation requires a plugin-owned session. SI/COMSI attachment remains read-only.
- `origin_open_project` protects the original by working on a copy.
- Existing output behavior must be explicit; ordinary project saving is non-overwriting.
- Stable refs can become stale after structural changes. Refresh the object audit once rather than
  guessing a new ref.
- Raw `origin_execute_labtalk` is an explicit advanced tool. Prefer typed worksheet, analysis,
  object, and graph tools when they cover the request.
- A successful call proves only its documented readback invariants. Human review remains required
  for scientific meaning.
