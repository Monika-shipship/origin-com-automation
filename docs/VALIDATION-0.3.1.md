# Origin COM Automation 0.3.1 Validation

Validation date: 2026-07-28

## Scope

This report covers the balanced fast workflow defaults and the synchronous `origin_run_task`
entry. It distinguishes fake-COM/unit evidence from bounded live Origin COM evidence.

## Automated Gates

- Unit suite: `327 passed`.
- Real stdio MCP transport: passed; 52 tools were listed, `origin_run_task` exposed an expanded
  schema, and `origin_health_check` returned a successful common envelope.
- Ruff: passed.
- mypy: passed across 52 source files.
- Source distribution and wheel: built successfully as `0.3.1`.
- `pip check`: no broken requirements.
- Release audit: passed for 140 tracked files.
- Distribution validator, official plugin validator, and Skill validator: passed.

## Live Origin Evidence

Bounded live smoke tests ran on Windows 11 x64 with Python 3.13 x64 and Origin `10.1.0.178` x64:

- Result: `8 passed, 1 skipped` in 143.25 seconds.
- The optional WSe2 feedback test was skipped because `ORIGIN_FEEDBACK_PROJECT` was not supplied.
- Covered owned start/shutdown, linked data, worksheet/formula readback, native analyses, graphs,
  PNG pixels, project save/reopen, Matrix, Image Page, Notes, folders, workflows, and serial batch.
- The pre-existing user-owned `Origin64` process was PID 44920 before the suite and remained the
  only Origin process afterward. No existing process was attached, closed, or terminated.

## Known Limits

- Synchronous `origin_run_task` is intended for ordinary complete tasks. Explicit task status and
  resume tools remain the supported route for intentionally checkpoint-heavy work.
- A fake controller or successful stdio schema call is not evidence of real Origin COM success.
