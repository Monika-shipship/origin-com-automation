# Origin COM Automation 0.2.0 Validation

Date: 2026-07-26

Candidate: `0.2.0+codex.20260726161056`

Environment: Windows 11 x64, Python 3.13 x64, Origin 10.1.0.178 x64

## Automated release gates

| Gate | Result |
|---|---|
| Python compilation | Passed for `src` and `tests` |
| Unit and MCP tests | 226 passed |
| Ruff | Passed |
| mypy | Passed for 43 source files |
| Wheel and source build | Passed for 0.2.0 |
| Dependency check | No broken requirements |
| Release audit | Passed for 104 tracked files before this report was added |
| Codex plugin validator | Passed |
| Skill validator | Passed |

## Live Origin 10.1 tests

All live tests used a fresh owned `Origin.Application` instance. The user's pre-existing Origin
process remained open, and every test confirmed that its newly created Origin process exited.

| Test | Result | Decisive checks |
|---|---|---|
| Mixed Excel workflow | Passed | 26-row mixed XLSX import, `Ion=2260...950`, numeric/text/mixed writes, readback, graph export, OPJU save |
| Native analysis operation | Passed | structured `fitlr`, dynamic output refs, operation query, input change, one recalculation, changed result |
| Connector and native objects | Passed | CSV connector create/refresh/disconnect, Matrix write/read/reopen, Image Page PNG import/dimensions/reopen, Note and Folder persistence |
| Graph workflow | Passed | graph-template discovery metadata, dual-Y command route, PNG preview, dimensions, nonblank ratio, unique colors |
| FigureSpec batch | Passed | two independent data-to-project specs, editable OPJU and PNG per item, distinct digests, QA and shutdown |
| WSe2 feedback project | Passed | direct A/B/C bindings, categorical styles and legend, five rendered colors, edit/restore pixel proof, save and reopen |

## Installed plugin verification

- Personal marketplace status: installed and enabled.
- Installed version: `0.2.0+codex.20260726161056`.
- Real stdio MCP transport: initialized, listed tools, and returned a successful
  `origin_health_check` response.
- Installed MCP tool count: 44.

## Verified capability boundary

Verified on Origin 10.1: safe owned sessions; mixed CSV/Excel import and write readback; local CSV
Data Connectors; Matrix create/read/write persistence; Image Page creation and PNG import; Notes;
Project Folder create/list/rename persistence; structured `fitlr` and its recalculating Analysis
Operation; scatter/line/column and categorical graph routes; preview pixel metrics; the
data-to-project FigureSpec route; two-item serial batch.

Supported-unverified: generic X-Functions beyond the verified registry entries, analysis
templates, Matrix transforms, Image Page export/conversion, folder move/delete, graph-template
application, complete dual-Y/inset binding behavior, and specialized 2D/3D/statistical graphs.
Those routes remain capability-gated and must not be reported as verified after a merely
non-throwing Origin command.

Unsupported: authenticated remote connectors and force termination based only on observed PID.
