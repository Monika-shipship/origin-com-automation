# Origin COM Automation 0.2.2 Validation

Candidate: `0.2.2+codex.20260728085857`

## Scope

0.2.2 is a maintenance update on the 0.2.1 execution path. It adds no MCP tools or workflow
stages. The public contract is 45 tools with the 0.2.1 canonical schema digest:

`4a71f5de9fd3028375d56608c9d61cd32dd959bbdff757a031cb1ea645a5b9fc`

## Automated validation

- Unit suite: `276 passed, 8 skipped`.
- Ruff: passed.
- mypy: passed for 53 source files.
- Wheel and source distribution build: passed for 0.2.2.
- Dependency check, distribution validator, release audit, plugin validator, and Skill validator: passed.
- Installed package: non-editable under the versioned `%LOCALAPPDATA%` runtime.
- Installed MCP stdio: health check passed; 45 tools exposed.
- Installed schema digest: `4a71f5de9fd3028375d56608c9d61cd32dd959bbdff757a031cb1ea645a5b9fc`.

## Live Origin validation

Validated with Origin `10.1.0.178` x64 and the installed external 0.2.2 runtime:

- Three bounded live tests passed in 48.29 seconds: linked Excel selection, linked connector refresh
  with `F(x)` recalculation, native fit operation save/reopen, graph preview, export, and pixel QA.
- A real MCP stdio workflow passed: owned background start, linked CSV import, Origin `F(x)`, native
  linear fit with an Analysis Operation, scatter plot, PNG export, OPJU save, and owned shutdown.
- The exported image and project were present and non-empty, and no pre-existing Origin process was
  touched.

## Known limits

- The runtime is Windows-only and requires a registered compatible Origin COM server.
- A source project is never overwritten by default.
- Origin version-specific X-Function, template, and graph behavior still requires live verification.
