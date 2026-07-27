# Origin COM Automation 0.3.0 Validation

Date: 2026-07-27

Candidate: `0.3.0+codex.20260727081330`

Environment: Windows 11 x64, Python 3.13 x64, Origin 10.1.0.178 x64

## Automated release gates

| Gate | Result |
|---|---|
| Unit and MCP tests | 317 passed |
| Ruff | Passed |
| mypy | Passed for 52 source files |
| Wheel and source build | Passed for 0.3.0 |
| Dependency check | No broken requirements |
| Release audit | Passed for 135 tracked files |
| Distribution validator | Passed |
| Codex plugin validator | Passed |
| Skill validator | Passed |

## Live Origin 10.1 tests

The full live smoke suite used fresh plugin-owned `Origin.Application` instances. Every owned
instance exited after its test. The user's pre-existing `Origin64` process, PID `44920`, remained
running and was neither attached to nor terminated.

Fresh final result: `8 passed, 1 skipped in 145.59s`. The skipped optional regression requires
`ORIGIN_FEEDBACK_PROJECT` to point to the separate WSe2 feedback OPJU fixture. The workflow-system
smoke test is included in the eight passing tests.

The workflow-system test proved one complete editable route:

- linked CSV import with source path and source hash retained;
- actual imported worksheet reference rebound for all later stages;
- Origin-native, auto-recalculating `differentiate` Analysis Operation;
- stable worksheet, analysis, graph, and artifact references;
- graph creation, PNG export, nonblank pixel and content-bounds checks;
- OPJU checkpoints, JSON/text manifests, and an Origin Notes manifest;
- project save, reopen, native operation query, and owned-process exit.

`dderivative` is still supported-unverified because its installed-version signature has not been
proved. The verified derivative route uses the installed Origin 10.1 `differentiate` X-Function
and forwards the scientific derivative method and order from `ScientificContract`.

## Workflow safety and execution evidence

- Offline planning reports all unresolved scientific decisions together before Origin starts.
- Execution is bound to an immutable workflow digest and an idempotency key.
- New high-level workflows receive a fresh controller and therefore cannot silently reuse the
  server's active low-level COM session. Explicit controller injection remains available for tests.
- Default execution starts a fresh plugin-owned, writable Origin instance with `exclusive=false`;
  `exclusive=true` remains restricted to read-only SI/COMSI attachment.
- Source files and source OPJU projects are never overwritten by default.
- Each result-defining mutation is verified before the next stage, and batch behavior is
  fail-fast by default.
- Formula, analysis, graph, manifest, and save stages write a phase ledger. Completed mutation
  keys are not replayed during resume.
- Pixel QA uses foreground content bounds as well as dimensions and nonblank checks, avoiding
  false failures on sparse scientific plots while still detecting clipping and excessive whitespace.

## Installed plugin verification

- Personal marketplace status: installed and enabled.
- Installed version: `0.3.0+codex.20260727081330`.
- Installed root:
  `%USERPROFILE%\.codex\plugins\cache\personal\origin-com-automation\0.3.0+codex.20260727081330`.
- Installed MCP tool count: 51.
- All six high-level workflow tools were present.
- Real stdio MCP transport initialized successfully and returned successful
  `origin_health_check`, workflow-scoped `origin_capabilities`, and offline
  `origin_plan_workflow` responses.
- Offline planning returned a nonempty digest and `executor_executable=true` without starting
  Origin.

## Known limits

An actual blocked or interrupted COM call followed by checkpoint resume has not yet been exercised
end to end. Checkpoint resume is therefore **supported-unverified**, even though digest, source-hash,
checkpoint-hash, and no-replay rules have unit coverage.

Generic X-Functions beyond the verified registry, analysis templates, Matrix transformations,
Image Page export/conversion, folder move/delete, graph-template application, complete dual-Y and
inset binding behavior, and specialized 2D/3D/statistical graphs retain their capability-specific
`supported_unverified` status. A non-throwing COM or LabTalk command is not accepted as proof that
one of these operations succeeded.

Authenticated remote connectors and force termination based only on an observed PID remain
unsupported.
