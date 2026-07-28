# Changelog

## [0.2.2] - 2026-07-28

This is a maintenance release built on the lean 0.2.1 execution path.

### Added

- Version-scoped non-editable runtime under `%LOCALAPPDATA%\OriginComAutomation\runtime\<plugin-version>`.
- Bootstrap lock and runtime metadata so concurrent launches cannot use a partial environment.
- Focused internal MCP, COM support, hashing, and runtime utility modules.

### Preserved

- Exactly 45 MCP tools, with unchanged schemas, defaults, result envelopes, error codes, and task steps.
- Direct FigureSpec execution, linked imports, Origin `F(x)` formulas, native Analysis Operations,
  ownership safeguards, recovery, non-overwrite saves, and bounded verification.

### Excluded

- No WorkflowSpec, workflow engine, planner, ledger, manifest, checkpoint, or new tool was added.

### Validation

- Unit and transport tests: see [0.2.2 validation](docs/VALIDATION-0.2.2.md).
- Real Origin tests are reported separately and are marked `未验证` when Origin is unavailable.

## [0.2.1]

- Added native Origin formulas, Analysis Operations, connectors, templates, graph preview, and recovery.
- Improved mixed-column import and write readback.
- Added owned-process tracking and poisoned-session recovery.

## [0.2.0]

- Added the initial structured Origin COM MCP surface for projects, worksheets, analyses, graphs, and exports.
- Centralized COM access on a serial STA worker and protected source projects by default.
