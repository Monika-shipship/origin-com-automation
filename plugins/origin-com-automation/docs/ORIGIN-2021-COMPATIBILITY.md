# Origin 2021 compatibility update

Date: 2026-08-22  
Fork manifest: `0.2.3+codex.20260822062434`  
Compatibility implementation: `9165e59`  
Upstream baseline: `origin/marketplace` at `6cd92ab` (v0.2.3 marketplace snapshot)

## Purpose

This update makes the existing Origin COM Automation plugin behave safely and
verifiably on OriginPro 2021 (9.8), without claiming that every Origin release exposes
the same COM, LabTalk, X-Function, export, or project-object behavior.

## Supported and verified environments

| Environment | Status | Evidence |
|---|---|---|
| Windows 10 x64, OriginPro 2021 `9.8.0.200`, Python `3.13.7` x64, SciPy `1.18.1` | **Verified for this fork** | 292 unit/regression tests; 41/41 targeted live checks against the source tree; 41/41 repeated against the installed package; FigureSpec preflight and successful end-to-end run; 45/45 MCP tools registered and health-checked. |
| Origin 2024b `10.1.0.178` | **Verified only for the original upstream v0.2.3 baseline** | The upstream validation record covers 2024b. The compatibility changes retain automated regression coverage, but this exact fork was not rerun live on 2024b. |
| Origin 2021b `9.85` through 2024a | **Version-dependent and not exhaustively live-tested** | The implementation uses capability gates and version-aware fallbacks. Do not infer full support from the version number alone. |
| Earlier than Origin 2021 `9.8` | **Unsupported/unverified** | No live validation evidence. |
| 32-bit Origin or 32-bit Python | **Unsupported** | The runtime requires a 64-bit registered Origin COM server and 64-bit Python 3.11 or newer. |

The 41-case matrix is a targeted behavioral suite, not merely tool discovery. It checks
data preservation, exact worksheet and matrix readback, analysis/session health, graph
state changes, Notes and folder effects, version gates, watermark rejection, save, and
clean shutdown. MCP registration (`45/45`) is reported separately and is not treated as
proof that all 45 tools completed every possible live action.

## Changes compared with upstream v0.2.3

| Area | Upstream behavior observed on Origin 2021 | Compatibility update |
|---|---|---|
| Partial worksheet writes | A successful ranged write could clear cells below the requested block. | Merge the affected columns, write once, and verify both the requested block and preserved surrounding cells. |
| Pivot and transpose | A numeric destination column could reject or corrupt text output. | Infer/set destination `DataFormat`, then verify dimensions, LongNames, and complete values. |
| MatrixObject offsets | Public `(row, column)` offsets did not match Origin 9.8 COM ordering; ranged `GetData` could ignore range arguments. | Adapt COM calls to `(column, row)`, read the full matrix, slice by the real offset, and verify exact placement. |
| Native analysis columns | Numeric column indices could reach LabTalk/X-Functions without normalization. | Resolve indices to Origin column names before native analysis. |
| Python/SciPy analysis | CPU/import work ran inside the serialized COM worker timeout and could poison an otherwise healthy session. | Run non-COM analysis outside the STA worker and confirm that subsequent COM readback remains healthy. |
| FigureSpec snapshot references | Plans could accept a worksheet reference that snapshot import would never create, then fail after mutation. | Derive the canonical `[Workbook]Sheet1` reference during preflight and propagate it through execution. |
| Task status | An inner `success=false` result could still be surfaced as a succeeded task. | Propagate inner failure state to the outer task result. |
| Graph layouts | Several commands used incorrect or incomplete LabTalk semantics and treated command acceptance as success. | Correct dual-Y, inset, link, grid, extract, merge, and add-layer commands; verify layer count, geometry, links, or newly created graph pages. |
| Notes | Text export/delete paths were not reliable on 9.8. | Use tested `save -n` and `window -cn` fallbacks and verify the artifact/object state. |
| Project Explorer folders | Folder move/delete routes were unreliable and could change `ActiveFolder`. | Use `pe_move`/`pe_rmdir` fallbacks, restore `ActiveFolder`, and verify the final tree. |
| Version-specific features | Unsupported Image Page, SVG, or graph-template routes could fail late or imply capability that 9.8 does not have. | Reject before mutation with `IMAGE_PAGE_UNSUPPORTED_VERSION`, `UNSUPPORTED_EXPORT_FOR_VERSION`, or `GRAPH_TEMPLATE_UNSUPPORTED_ON_VERSION`. |
| Export licensing | A watermarked export could be reported as a successful deliverable. | Detect repeated cyan demo bands in PNG/TIFF and repeated demo text in PDF; return `LICENSE_WATERMARK_DETECTED` while retaining the file for diagnosis. |
| Timeout recovery | Recovery requirements were not explicit enough to prevent cross-process retry assumptions. | Return `recovery_requires_same_server=true` and regression-test controller replacement and next-start readiness. |

## Origin 2021 (9.8) feature boundaries

- **Real Image Pages:** unavailable; Origin 2021b (9.85) or newer is required.
- **SVG through `expGraph`:** unavailable; use a supported raster/PDF route when licensing permits.
- **Apply OTP to an existing graph:** blocked because no non-destructive adapter was verified for 9.8.
- **PNG/TIFF/PDF under a demo license:** exported files may exist, but detected watermarks make them invalid deliverables.
- **No license bypass:** the update detects and reports licensing artifacts; it does not remove them.

## Validation summary

- Unit and regression tests: `292 passed`.
- Origin 2021 targeted live matrix from source: `41/41` expectations met.
- Origin 2021 targeted live matrix from installed plugin: `41/41` expectations met.
- FigureSpec: invalid snapshot reference blocked in preflight; valid `[WFFix]Sheet1` flow completed import, plot, save, QA, and shutdown.
- Installed MCP surface: `45/45` tools registered; health check reported 64-bit Python/Origin, Origin `9.8.0.200`, and SciPy `1.18.1`.
- Process hygiene: no Origin process remained after the validation run.

## Safety notes

- Work on copied projects and save to a new OPJU unless source replacement is explicitly requested and protected by the existing confirmation/hash/backup flow.
- Capability gates are not a substitute for a live test on an unlisted Origin release.
- Scientific results still require review of ranges, models, constraints, units, transformations, and source data.
- This fork is independent software and is not affiliated with or endorsed by OriginLab.

## Related report

The upstream tracking issue contains the full problem statement and proposed integration
checklist: [Dawn-zxj/origin-com-automation#1](https://github.com/Dawn-zxj/origin-com-automation/issues/1).
