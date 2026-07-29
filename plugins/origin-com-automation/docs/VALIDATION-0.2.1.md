# Origin COM Automation 0.2.1 Validation

Date: 2026-07-27

Candidate: `0.2.1+codex.20260726181655`

Environment: Windows 11 x64, Python 3.13 x64, Origin 10.1.0.178 x64

## Automated release gates

| Gate | Result |
|---|---|
| Python compilation | Passed for `src` and `tests` |
| Unit and MCP tests | 266 passed |
| Bilingual README contract | English/Chinese section order, 45 tools, local links, defaults, architecture, and disclaimers verified |
| Ruff | Passed |
| mypy | Passed for 44 source files |
| Wheel and source build | Passed for 0.2.1 |
| Dependency check | No broken requirements |
| Release audit | Passed |
| Codex plugin validator | Passed |
| Skill validator | Passed |
| Distribution validator | Passed |

## Live Origin 10.1 tests

All live tests used fresh plugin-owned `Origin.Application` instances. Each test confirmed that
its owned process exited and that the pre-existing Origin process present at test start remained.

| Test | Result | Decisive checks |
|---|---|---|
| Native editable defaults | Passed | Default linked CSV, source refresh, auto `F(x)` formula, native `fitlr`, save/reopen persistence, no Python fallback |
| Excel linked import | Passed | Selected non-first `Target` sheet, preserved `x/y` long names, retained both data rows with one-row header semantics |
| Native analysis operation | Passed | Structured `fitlr`, operation query, source-file edit, connector refresh, recalculation, changed result |
| Connector and native objects | Passed | Explicit CSV header, connector lifecycle, Matrix, Image Page, Notes and Project Folder persistence |
| Mixed data and graph workflow | Passed | Mixed XLSX snapshot import, verified worksheet writes, graph export, OPJU save |
| Graph workflow | Passed | Template discovery, dual-Y route, PNG preview dimensions, nonblank and color checks |
| FigureSpec batch | Passed | Two independent editable data-to-project specs with distinct digests, OPJU/PNG artifacts and QA |

Result: `7 passed, 1 skipped in 100.09s`. The skipped optional test requires
`ORIGIN_FEEDBACK_PROJECT` to point to the separate WSe2 feedback OPJU fixture.

## Installed plugin verification

- Personal marketplace status: installed and enabled.
- Installed version: `0.2.1+codex.20260726181655`.
- Installed root: `%USERPROFILE%\.codex\plugins\cache\personal\origin-com-automation\0.2.1+codex.20260726181655`.
- Real stdio MCP transport: initialized, listed tools, and returned successful
  `origin_health_check` and `origin_capabilities` responses.
- Installed MCP tool count: 45.
- Required tools confirmed: `origin_import_data`, `origin_manage_connector`,
  `origin_set_column_formula`, `origin_run_analysis`, and `origin_recover_session`.

## Verified 0.2.1 behavior

- CSV, TSV, and Excel imports use a retained Origin Data Connector by default; snapshot import
  remains an explicit compatibility mode.
- Explicit Excel header handling uses Origin's one-row long-name configuration and preserves all
  data rows, including when selecting a non-first workbook sheet.
- Connector creation and refresh flush pending automatic recalculation.
- Derived columns use persistent Origin `F(x)` formulas by default and verify formula metadata and
  calculated values.
- Default linear fitting creates an auto-recalculating Origin `fitlr` Analysis Operation.
- Unsupported native requests fail without creating output objects or silently running Python.
- Linked connector, formula, values, and native operation persist after OPJU save and reopen.

## Known limits

Generic X-Functions beyond the verified registry, analysis templates, Matrix transformations,
Image Page export/conversion, folder move/delete, graph-template application, full dual-Y/inset
binding behavior, and specialized 2D/3D/statistical graphs remain supported-unverified unless a
version-specific live test proves their output. Authenticated remote connectors and force
termination based only on an observed PID remain unsupported.
