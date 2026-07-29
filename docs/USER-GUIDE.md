# Origin COM Automation User Guide

This guide helps an Origin user give Codex enough information to produce an editable, reviewable
result. You do not need to know COM or MCP. For installation, start with the
[README](../README.md); for exact tool inputs, use the [Tool Reference](TOOL-REFERENCE.md).

## Request Template

Include these six fields in order. Replace the examples with your real paths, names, and methods.

1. **Source:** file path, file type, Excel sheet if relevant, and linked or snapshot intent.
2. **Worksheet:** destination name for new data or exact `[Book]Sheet` for an existing project.
3. **X/Y:** X column and every Y, error, label, or grouping column with units.
4. **Range or branch:** inclusive rows, filters, scan direction, and forward/reverse branch.
5. **Analysis or method:** exact fit/transform/derivative plus model, constraints, and parameters.
6. **Graph or output:** plot type, layout/style requirements, OPJU path, export path, and format.

A strong request also says what must be preserved, what may be changed, and what Codex must verify.
For example: “Do not overwrite the source OPJU; verify X/Y bindings, the Analysis Operation, the
saved project, and the exported PNG.”

## Ready-To-Use Example Prompts

### New data

> Use Origin in the background. Inspect `C:\data\transfer.xlsx`, then import sheet `Data` into a
> new workbook as linked data. Use column A (`Vg`, V) as X and column B (`Id`, A) as Y, all rows in
> the existing order, with no analysis. Create an editable scatter graph, save a new project as
> `C:\results\transfer.opju`, export `C:\results\transfer.png`, and verify the connector, row count,
> X/Y binding, project file, and image content.

Typical route: `origin_inspect_data_source`, `origin_start`, `origin_import_data`,
`origin_read_worksheet`, `origin_create_graph`, `origin_save_project_copy`,
`origin_export_graph`, and `origin_shutdown`.

### Existing OPJU

> Open a protected working copy of `C:\data\device.opju`. List the actual objects and find graph
> `TransferGraph`. Change only its Y axis to log scale and refresh its legend without changing the
> worksheet binding. Save as `C:\results\device-reviewed.opju`, export a PNG, and verify the graph
> binding and both artifacts. Never overwrite or close the source project as if it were owned.

Typical route: `origin_start`, `origin_open_project`, `origin_list_objects`,
`origin_configure_graph`, `origin_view_graph`, `origin_save_project_copy`, and
`origin_export_graph`.

### Native fit

> Import `C:\data\calibration.csv` as linked data. Use the full A and B columns as X and Y,
> with no filtering and `row_order="as_is"`. Run the verified Origin-native linear-fit method with
> an editable Analysis Operation and automatic recalculation. Plot the data and fit together, save
> a new OPJU, and verify the operation ref, recalculation state, graph sources, and saved file. Do
> not substitute a Python fit if the native route is unavailable.

Typical route: `origin_import_data`, `origin_run_analysis`,
`origin_get_analysis_operation`, `origin_recalculate_analysis`, `origin_create_plot`, and
`origin_save_project_copy` (the public save-copy tool used for project output).

### Multi-series plot

> Open a working copy of `C:\data\temperature.opju`. In `[Book1]Data`, use A (`Temperature`, K) as
> X and B, C, D as three Y series. Create one line-and-symbol graph using distinct accessible
> colors, consistent line widths and marker sizes, long-name legend entries, axis titles with units,
> and sensible linear limits. Do not add a fit. Export a vector PDF and 600 dpi PNG, preview the
> graph, and verify that all three plots are bound to the requested columns.

Typical route: `origin_open_project`, `origin_create_plot`, `origin_configure_graph`,
`origin_view_graph`, `origin_export_graph`, and `origin_save_project_copy`.

## Practical Critical Paths

### Diagnose without opening Origin

Ask Codex to call `origin_health_check` once. It checks Python/Origin bitness, dependencies,
registered ProgIDs, executable access, temporary-directory write access, active Origin processes,
and watchdog-like scheduled tasks without activating COM. Use `origin_capabilities` when the task
depends on a specialized feature or an Origin version other than the verified release.

### Build a project from CSV or Excel

1. Profile the source with `origin_inspect_data_source`.
2. Start an owned, usually hidden session with `origin_start`.
3. Import with `origin_import_data`; the default `source_mode="linked"` creates a local Data
   Connector. Use `source_mode="snapshot"` only for an intentional static copy.
4. Read only the defining X/Y range with `origin_read_worksheet` and stop if it is empty or wrong.
5. Add editable calculations with `origin_set_column_formula`, which stores Origin `F(x)`.
6. Run a requested analysis with `origin_run_analysis`, create the graph with
   `origin_create_plot` or `origin_create_graph`, then style it in one `origin_configure_graph` call.
7. Save separately with `origin_save_project_copy`, export with `origin_export_graph`, and use
   `origin_view_graph` for a visual artifact check.
8. Call `origin_shutdown`; it exits only a plugin-owned Origin instance.

### Modify an existing project

Use `origin_open_project`, which copies the OPJU before opening it. Call `origin_list_objects` once
to get stable refs, change only named objects, save to a distinct path with
`origin_save_project_copy`, and reopen only when persistence needs proof. Ordinary saving cannot
overwrite the protected source. Source replacement is a separate, intentionally strict operation.

### Inspect a user's open Origin session

Explicit SI/COMSI attachment is read-only even when `exclusive=true`. Use it for listing, targeted
worksheet reads, previews, and exports. Mutation, save, shutdown, and reclassification as owned are
rejected. Process IDs are audit evidence, not ownership proof.

### Recover after a timeout

After `COM_TIMEOUT`, do not send more work or an ordinary shutdown to the blocked worker. Call
`origin_recover_session`, review the returned process audit, then call `origin_start`. Read-only
operations may retry once for known transient RPC busy errors; mutations are never blindly replayed.

## Getting Better AI Plots

- Name the scientific role of each column: X, Y, X error, Y error, label, grouping, or color scale.
- Give long names and units, or ask Codex to preserve those already in the worksheet.
- Specify the graph family and scale. Say scatter, line, column, heatmap, contour, dual-Y, inset, or
  multi-panel rather than “make it look good.”
- State comparisons that matter. Ask for a shared scale, aligned panels, consistent colors, or a
  fixed series order when visual comparison is the goal.
- State required accessibility or publication rules: colorblind-safe palette, monochrome-safe
  markers, vector PDF, raster DPI, journal dimensions, or font requirements.
- Ask for one combined styling pass after the data bindings are correct. Repeated speculative edits
  cost time and can obscure what changed.
- Ask Codex to preview and inspect the graph, then verify plot-to-column bindings and exported files.
  Pixel checks can detect a blank or missing-color image; they do not judge scientific meaning.
- Provide an Origin template path only when you trust that template. Template application is
  digest-locked and checks layer compatibility, but the user remains responsible for its design.

## Editable Analysis Rules

`origin_run_analysis` defaults to `backend="origin_native"`, `create_operation=true`, and
`recalculate_mode="auto"`. The verified linear-fit route invokes Origin's native `fitlr`, resolves
its dynamic output refs, and returns an operation ref that can be inspected or recalculated. An
unmapped native method fails instead of silently pasting NumPy/SciPy results into the workbook.

`backend="python"` is an explicit compatibility choice for supported methods such as descriptive
statistics, polynomial fitting, smoothing, derivatives, peak analysis, FFT, statistical tests, and
configured nonlinear models. Such results are labeled as not editable in Origin and as having no
native Analysis Operation.

Never leave branch, row range, filters, derivative method, smoothing window, polynomial degree,
missing-value policy, normalization, model, or constraints implicit when they affect the result.
Ranges are inclusive and 0-based at the tool layer; filters are AND-combined; row order is
`as_is` or `reverse`.

## Data Connections And Formulas

Linked CSV/Excel import records and checks the canonical source path, source hash, connector state,
selected sheet, header policy, shape, labels, and column profiles. For Excel, a requested non-first
sheet is passed to the connector and read back. A snapshot instead copies mixed values and validates
each source column against Origin readback.

`origin_set_column_formula` preserves Formula, Before Formula Script, FormulaRange, and
recalculation mode. `origin_write_worksheet` is for intentional materialized values; it checks the
COM result, flushes pending recalculation, and reads the rectangle back.

## Verification Boundaries

A COM call returning without an exception is not enough. Imports compare profiles, writes read back
cells, native operations are queried after creation, saves check file state and may reopen, exports
inspect the actual file, and previews decode pixels. Verification proves explicit invariants, not
the scientific correctness of an unspecified method. Back up important data and review every
consequential output.
