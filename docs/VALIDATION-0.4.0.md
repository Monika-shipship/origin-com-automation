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
- Worktree: `feature/v0.4-consolidation`
- Plugin version: `0.4.0`

## Automated gates

The final values below are filled from fresh commands before the local branch is merged:

| Gate | Result |
|---|---|
| Unit tests | **340 passed** |
| Ruff | **passed** |
| mypy | **passed** |
| Build and pip check | **passed**; `origin_com_automation-0.4.0` artifacts built |
| Release audit | **passed**; 140 tracked files |
| Distribution/plugin/Skill validators | **passed** |
| Real stdio transport | **passed**; 52 tools and expanded schemas |
| Live Origin smoke | **not verified in this run**; 9 tests skipped because user-owned PID 44920 was already running |

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
this validation. The live suite refused to attach while it was running. The plugin does not disable
or delete cleanup watchdog tasks.

## Known limits

- If Origin is unavailable, the live smoke suite is marked **not verified** rather than inferred from
  fake COM tests.
- Origin-specific X-Function, graph-template, and specialized graph behavior remains capability- and
  version-gated until exercised on the installed Origin release.
