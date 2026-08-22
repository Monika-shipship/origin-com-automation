<p align="center">
  <img src="assets/origin-automation-logo.png" width="160" alt="Origin COM Automation logo">
</p>
<h1 align="center">Origin COM Automation</h1>
<p align="center">Ask Codex to turn data and existing Origin projects into editable analyses, graphs, and verified output files.</p>
<p align="center">
  <a href="https://github.com/Dawn-zxj/origin-com-automation/releases/tag/v0.2.3"><img alt="Stable v0.2.3" src="https://img.shields.io/badge/stable-v0.2.3-DF5B3F"></a>
  <a href="https://github.com/Dawn-zxj/origin-com-automation/actions/workflows/unit-tests.yml"><img alt="Release gates" src="https://img.shields.io/badge/release-gates-2E7D6E"></a>
  <a href="#requirements"><img alt="Windows x64" src="https://img.shields.io/badge/Windows-x64-0078D4"></a>
  <a href="#requirements"><img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776AB"></a>
  <a href="docs/VALIDATION-0.2.3.md"><img alt="Origin verified 2024b" src="https://img.shields.io/badge/Origin_verified-2024b-DF5B3F"></a>
  <a href="#installation"><img alt="Codex Plugin" src="https://img.shields.io/badge/Codex-Plugin-111111"></a>
  <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/license-MIT-2E7D6E"></a>
</p>
<p align="center"><strong>English</strong> | <a href="README.zh-CN.md">简体中文</a></p>

<!-- section:what-it-does -->
## What It Does

Origin COM Automation lets Codex work with Origin in the background while keeping your result
editable in Origin. Give it a CSV, Excel workbook, or OPJU project and describe the worksheet,
columns, method, graph, and output you need. It can preserve source links, create Origin formulas
and native Analysis Operations, save a separate project, export figures, and check the result.

<!-- section:capabilities -->
## Capabilities

- Import CSV, TSV, XLS, XLSX, and XLSM data or open a protected working copy of an OPJU project.
- Keep imported data linked to its source, or make an explicit disconnected snapshot.
- Create editable calculated columns as Origin `F(x)` formulas.
- Run a verified Origin-native linear fit as a recalculating Analysis Operation; broader methods
  are available only through explicit, clearly labeled compatibility routes.
- Create and modify graphs, including series, axes, legends, layouts, templates, and export options.
- Read and edit worksheets, matrices, Image Pages, Notes, and Project Explorer folders.
- Save a new OPJU, export version-supported graph formats, preview graphs, and verify bindings,
  artifacts, and demo-license watermark status. Origin 9.8 supports PNG/TIFF/PDF but not SVG.

The compatibility update in manifest `0.2.3+codex.20260822062434` was live-tested on
OriginPro 2021 `9.8.0.200`. See the
[Origin 2021 compatibility record](docs/ORIGIN-2021-COMPATIBILITY.md) for the exact version
matrix, changes from upstream v0.2.3, test evidence, and known limits.

<!-- section:ask-codex -->
## What To Tell Codex

Include these six details. Codex can inspect names, but it should not invent scientific choices.

1. **Source:** the CSV, Excel, or OPJU path and whether it should stay linked.
2. **Worksheet:** the sheet name or existing Origin worksheet to use.
3. **X/Y:** the exact X and Y columns, including every Y series.
4. **Range or branch:** row limits, sweep direction, filters, or branch selection.
5. **Analysis or method:** the fit, derivative, transform, model, and critical parameters.
6. **Graph or output:** graph type, styling needs, new OPJU path, and export path/format.

<!-- section:examples -->
## Ready-To-Use Prompts

### New data

> Use Origin in the background. Import `C:\data\transfer.xlsx`, sheet `Data`, as linked data.
> Use column A as X and B as Y, all rows, with no analysis. Create an editable scatter graph,
> save a new project to `C:\results\transfer.opju`, export `transfer.png`, and verify the source
> link, X/Y binding, row count, saved project, and image.

### Existing OPJU

> Open a working copy of `C:\data\device.opju`. Inspect the actual worksheet and graph names,
> change only graph `TransferGraph` to log-scale Y with a refreshed legend, preserve its source
> binding, save as `C:\results\device-reviewed.opju`, and do not overwrite the original.

### Native fit

> Import `C:\data\calibration.csv` as linked data. In the imported worksheet use A as X and B as
> Y over the full columns in their existing order. Run an Origin-native linear fit with an editable,
> automatically recalculating Analysis Operation, plot data plus fit, save a new OPJU, and verify
> the operation and graph bindings.

### Multi-series plot

> Open a working copy of `C:\data\temperature.opju`. In `[Book1]Data`, use A as X and B, C, D as
> Y. Create one line-and-symbol graph with distinct accessible colors, clear long-name legend
> entries, axis titles with units, and no analysis. Export PDF and 600 dpi PNG, then verify every
> series binding and both files.

For more request patterns and critical paths, see the [User Guide](docs/USER-GUIDE.md).

<!-- section:installation -->
## Installation

Install the stable plugin from its Git marketplace:

```powershell
codex plugin marketplace add Dawn-zxj/origin-com-automation --ref marketplace
codex plugin add origin-com-automation@origin-automation-marketplace
```

Start a new Codex task after installation so the task loads the plugin's current tools and icon.

To update, refresh the marketplace and install the plugin again, then start a new Codex task:

```powershell
codex plugin marketplace upgrade origin-automation-marketplace
codex plugin add origin-com-automation@origin-automation-marketplace
```

As a fallback, download the plugin ZIP from the
[v0.2.3 release](https://github.com/Dawn-zxj/origin-com-automation/releases/tag/v0.2.3),
extract it, run `scripts\bootstrap.ps1`, and install that local plugin directory in Codex.

<a id="requirements"></a>
### Requirements

- 64-bit Windows and 64-bit Python 3.11 or newer.
- This compatibility fork is live-verified on OriginPro 2021 `9.8.0.200`.
- The original upstream v0.2.3 baseline was live-verified on Origin 2024b `10.1.0.178`; this
  compatibility commit has regression coverage but was not rerun live on 2024b.
- Origin 2021b `9.85` through 2024a remains version-dependent until each release is live-tested.
- Releases earlier than Origin 2021 `9.8`, 32-bit Origin, and 32-bit Python are unsupported.
- A registered `Origin.Application`, `Origin.ApplicationCOMSI`, or `Origin.ApplicationSI` ProgID.
- Codex with local plugin and MCP support.

The bootstrap creates a version-scoped runtime under
`%LOCALAPPDATA%\OriginComAutomation\runtime\<plugin-version>`; it does not modify system Python.

<!-- section:defaults -->
## Safe, Editable Defaults

- Imports use `source_mode="linked"`; choose `source_mode="snapshot"` only for an intentional
  disconnected copy.
- Derived columns use `origin_set_column_formula`, so the calculation remains an editable Origin
  `F(x)` formula.
- Analysis uses `backend="origin_native"`, `create_operation=true`, and
  `recalculate_mode="auto"` when a verified native mapping exists. It does not silently fall back
  to pasted Python results.
- Source projects are protected: normal work saves a separate OPJU and will not overwrite the
  source. Replacing a source requires explicit confirmations, hash checks, reopen validation, and
  a backup by default.
- Verification is bounded around defining data, bindings, operations, saves, and exports instead
  of repeating full discovery after every healthy step.
- Critical scientific parameters such as branch, range, filters, model, constraints, derivative
  method, smoothing, and units are not guessed.
- After `COM_TIMEOUT`, use `origin_recover_session` on the same MCP server process and then start a
  fresh owned Origin session.

<!-- section:scope-limits -->
## Verified Scope And Limits

| Status | Meaning |
|---|---|
| Verified in this fork | OriginPro 2021 `9.8.0.200`: 292 unit/regression tests, 41/41 targeted live checks against both source and installed package, FigureSpec preflight/end-to-end validation, and 45/45 MCP tool registration plus health checks. |
| Verified upstream baseline | Original v0.2.3 on Origin 2024b `10.1.0.178`; do not treat this as a live 2024b rerun of the compatibility commit. |
| Version-dependent | Generic allowlisted X-Functions, analysis templates, specialized graph families, some layout/template operations, and less common Matrix/Image/Folder actions require capability checks and explicit opt-in where requested. |
| Unsupported | Authenticated remote connectors, treating a PID difference as proof of COM ownership, or force-terminating Origin from PID observation alone. |

Origin 2021 (9.8) does not expose real Image Pages (introduced in 9.85), does not support SVG via
`expGraph`, and has no verified non-destructive adapter for applying an OTP to an existing graph.
These routes fail before mutation with version-specific errors. Raster/PDF exports that contain the
Origin demo watermark are retained only as diagnostic artifacts and are not reported as successful
deliverables.

The plugin never treats “no exception” as proof that a scientific result is correct. Check
`origin_capabilities` for the detected Origin version and the
[0.2.3 validation record](docs/VALIDATION-0.2.3.md) for exact evidence.

<!-- section:troubleshooting -->
## Troubleshooting

- **Old icon or tools:** upgrade the marketplace, install the plugin again, and start a new Codex
  task. Existing tasks retain the tool schemas and assets loaded when they began.
- **Origin will not start:** run `scripts\diagnose.ps1`; check that Python and Origin are both
  64-bit, a supported ProgID is registered, and no existing Origin or cleanup task is interfering.
- **Linked data did not refresh:** confirm the source path and Excel sheet, then ask Codex to inspect
  and refresh the Data Connector. A snapshot has no connector by design.
- **Timeout:** stop sending work to that session. Ask Codex to call `origin_recover_session`, then
  `origin_start`; mutating calls are not blindly replayed.

More detail is in the [User Guide](docs/USER-GUIDE.md) and
[Tool Reference](docs/TOOL-REFERENCE.md).

<!-- section:architecture -->
## Architecture

```mermaid
flowchart LR
    Codex["Codex"] --> MCP["Local MCP server"]
    MCP --> Controller["Safety controller"]
    Controller --> STA["Serialized STA worker"]
    STA --> Origin["Origin"]
    Origin --> Artifacts["Editable and exported artifacts"]
    Artifacts --> Controller
    Controller --> Codex
```

Everything runs locally. Codex sends structured requests to a local server; one serialized worker
controls Origin; the controller protects source projects and returns verified readback. See
[Architecture](docs/ARCHITECTURE.md) for session ownership, modules, runtime, error handling, and
workflow details.

<!-- section:disclaimer -->
## Disclaimer

This is an independent open-source project and is **not affiliated with or endorsed by OriginLab**.
Origin, OriginPro, LabTalk, and X-Function are products or technologies of OriginLab Corporation;
all related names and trademarks belong to their respective owners.

This plugin is research automation software, not scientific, engineering, legal, regulatory, or
commercial advice. Always **back up important projects and source data** and **review and validate outputs**
before using them in publications, decisions, fabrication, measurement, or other
consequential work. You remain responsible for methods, ranges, branches, filters, units, models,
constraints, source data, templates, licenses, and interpretation.

The software is provided under the [MIT License](LICENSE), without warranty of any kind.

<!-- section:references -->
## References

- [User Guide](docs/USER-GUIDE.md)
- [Complete Tool Reference](docs/TOOL-REFERENCE.md)
- [Architecture And Safety](docs/ARCHITECTURE.md)
- [Validation for 0.2.3](docs/VALIDATION-0.2.3.md)
- [Origin 2021 compatibility update](docs/ORIGIN-2021-COMPATIBILITY.md)
- [Previous validation: 0.2.0](docs/VALIDATION-0.2.0.md), [0.2.1](docs/VALIDATION-0.2.1.md), and [0.2.2](docs/VALIDATION-0.2.2.md)
- [Experimental Version Archive](docs/EXPERIMENTAL-VERSIONS.md)
- [References And Attribution](docs/REFERENCES.md)
- [MIT License](LICENSE)
