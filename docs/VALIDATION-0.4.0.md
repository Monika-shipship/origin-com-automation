# Origin COM Automation 0.4.0 Validation

This document records the local 0.4.0 release checks. It is intentionally separate from the
historical 0.3.1 evidence and does not claim that a simulated COM test is a live Origin test.

## Scope

- Consolidate duplicate MCP, workflow, graph, COM-support, and hashing implementations.
- Replace the copied editable runtime with an external versioned non-editable runtime.
- Preserve the 52-tool surface, 0.3.1 fast path, native-analysis default, and ownership boundaries.

## Environment

- OS: Windows x64
- Python: 3.13 x64
- Origin target: 10.1.0.178 x64 when the live suite is available
- Branch: local `main`
- Plugin version: `0.4.0`

## Automated gates

The values below come from fresh commands against local `main` and the installed plugin cache:

| Gate | Result |
|---|---|
| Unit tests | **347 passed** |
| Ruff | **passed** |
| mypy | **passed** |
| Build and pip check | **passed**; `origin_com_automation-0.4.0` artifacts built |
| Release audit | **passed**; 140 tracked files |
| Distribution/plugin/Skill validators | **passed** |
| Real stdio transport | **passed**; 52 tools and expanded schemas |
| Live Origin smoke | **not verified in this run**; 9 tests skipped because user-owned PID 44920 was already running |

## Installed-cache audit

- Installed manifest: `0.4.0+codex.20260728055733`.
- Clean plugin cache: **54.52 MiB**; no `.venv`, `.mypy_cache`, `build`, or generated
  `origin_com_automation.egg-info` directory remained after bootstrap.
- External runtime: **327.53 MiB** under
  `%LOCALAPPDATA%\OriginComAutomation\runtime\0.4.0+codex.20260728055733`.
- Installed package metadata reports `0.4.0`, and the imported package path resolves from the
  external runtime `site-packages`, not the plugin cache or development checkout.
- Installed stdio MCP initialization passed with **52 tools**, expanded `origin_run_task` schema,
  and a successful `origin_health_check` response.
- Bootstrap removes only transient build directories that it created itself; pre-existing
  developer build directories are preserved.

## Native-result regression checks

- A workflow that returns materialized/Python analysis data while native operations are required now
  fails with `NATIVE_ANALYSIS_UNCONFIRMED`.
- A formula step without verified Origin metadata and value readback now fails with
  `ORIGIN_FORMULA_UNCONFIRMED`.
- `fit_and_plot` and `statistical_summary` reject plans without an explicit analysis step.
- The workflow executor forwards one contiguous formula range and blocks unsupported branch/filter
  semantics instead of silently applying a different range.

## Architecture evidence

- `FigureSpec` compiles to `WorkflowSpec` and executes through `WorkflowEngine`.
- Both public task-status names read the same `TaskManager` record.
- Typed and role-based graph creation uses `graphs.catalog` metadata.
- MCP schemas are expanded in tool JSON Schema rather than appearing as `unknown` objects.
- Worksheet, graph, and project helpers are import-compatible from `origin_api.py` while residing in
  dedicated support modules.
- File hashing and canonical model digest values remain stable.
- The launcher resolves `%LOCALAPPDATA%\OriginComAutomation\runtime\<manifest-version>` and uses
  non-editable installation; the runtime import path must not be the development checkout.

## Live-process boundary

The pre-existing user Origin process `PID 44920` is not plugin-owned and remained untouched during
this validation, including across the installed-cache bootstrap and stdio health check. The live
suite refused to attach while it was running. The plugin does not disable or delete cleanup
watchdog tasks.

## Known limits

- If Origin is unavailable, the live smoke suite is marked **not verified** rather than inferred from
  fake COM tests.
- Origin-specific X-Function, graph-template, and specialized graph behavior remains capability- and
  version-gated until exercised on the installed Origin release.
