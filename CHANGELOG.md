# Changelog

All notable changes to Origin COM Automation are recorded here. The format follows Keep a
Changelog, and the project uses semantic versioning. Validation statements distinguish fake-COM
tests from real Origin COM tests.

## [0.3.0] - 2026-07-27

### Added

- Added the strict `WorkflowSpec` contract and six high-level MCP tools for offline planning,
  digest-bound execution, status, checkpoint resume, targeted audit, and manifest export.
- Added one-shot scientific parameter contracts, irregular CSV/Excel header previews, stable
  object references, plugin-owned helper ranges, phase ledgers, OPJU checkpoints, graph layout QA,
  clipping checks, and JSON/text/Origin Notes reproducibility manifests.
- Added version-aware native expression planning. Verified scalar Origin functions are preferred;
  the installed Origin 10.1 `differentiate` X-Function contract is registered, while
  `dderivative` remains supported-unverified until its exact live signature is proven.

### Changed

- The recommended route is now `plan -> validate -> execute`: collect all `required_decisions`
  once, approve one immutable digest, execute with an `idempotency_key`, then audit only named
  result objects.
- Batch work defaults to `fail_fast=true`. Completed mutation keys are not replayed during resume.
- Native Origin formulas, X-Functions, and Analysis Operations are selected before an external
  backend. Python runs only under the explicit `external_explicit` policy.

### Safety

- Execution requires a fresh plugin-owned Origin session, never mutates an attached user session,
  never overwrites source data or OPJU by default, and verifies every result-defining mutation.
- Resume verifies the workflow digest, source hashes, checkpoint hash, and prior stage outputs.

### Validation

- Unit and real stdio MCP transport coverage validate planning, schemas, idempotency, checkpoints,
  audits, manifests, and graph QA without requiring Origin.
- Real Origin 10.1 validation proved the complete linked-data workflow, native auto-recalculating
  `differentiate` operation, graph, PNG pixels, manifests, OPJU reopen, and owned-process exit.
  Fake COM tests are never reported as real COM success.

### Known limits

- Interrupted-session checkpoint resume remains supported-unverified until a bounded live
  interruption test proves it without replaying a completed mutation.
- Specialized graph families and template routes retain their per-capability verification status.

## [0.2.1] - 2026-07-26

### Added

- Added persistent local CSV/Excel Data Connectors, editable Origin `F(x)` columns, verified native
  `fitlr` Analysis Operations, and synchronized English and Chinese documentation.

### Changed

- Linked import and Origin-native auto-recalculating analysis became the public defaults.
- Python analysis became an explicit non-recalculating compatibility choice.

### Safety

- Source files stayed connected but protected; formulas and native operations required metadata
  and result readback rather than accepting a non-throwing command.

### Validation

- Origin 10.1 live validation covered linked CSV/Excel, formula persistence, native linear fit,
  OPJU save/reopen, graph export, Matrix, Image Page, Notes, folders, FigureSpec, and serial batch.

### Known limits

- Native high-level analysis mapping was limited mainly to verified linear fit and FFT options.

## [0.2.0] - 2026-07-26

### Added

- Expanded the plugin with structured X-Functions, Analysis Operations, Data Connectors, worksheet
  transforms, Matrix and Image Page tools, graph families, templates, layouts, previews,
  Project Folder, Notes, FigureSpec, batching, capability reporting, and local knowledge lookup.

### Changed

- Specialized operations moved behind explicit capability states: `verified`,
  `supported_unverified`, or `unsupported`.

### Safety

- Added strict schemas, stable refs, source/template hashes, non-overwrite defaults, and pixel/file
  checks for exported artifacts.

### Validation

- `docs/VALIDATION-0.2.0.md` records unit, transport, packaging, and bounded Origin smoke evidence.

### Known limits

- Several 3D/statistical graphs, templates, Matrix transforms, and analysis templates were exposed
  only as supported-unverified routes.

## [0.1.0] - 2026-07-25

### Added

- Initial personal Codex plugin with a local Python MCP server, pywin32 Origin COM controller,
  serialized STA worker, project and worksheet tools, structured analysis, plotting, export,
  health checks, LabTalk, recovery, tests, and installation scripts.

### Changed

- Established the common result envelope used by all public tools.

### Safety

- Protected source OPJU files, distinguished owned from attached sessions, refused to close user
  sessions, avoided PID-based termination, and validated saves and graph artifacts.

### Validation

- Unit tests used fake COM objects; bounded live smoke tests were separately identified when run.

### Known limits

- The initial release was primarily a focused low-level tool collection without intent planning,
  stable workflow digests, native operation breadth, or checkpoint resume.

[0.3.0]: https://github.com/Sheldon12311815/origin-com-automation/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/Sheldon12311815/origin-com-automation/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Sheldon12311815/origin-com-automation/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Sheldon12311815/origin-com-automation/releases/tag/v0.1.0
