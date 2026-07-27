# Changelog

All notable changes to `origin-com-automation` are documented here. The project follows a
non-overwriting, local-release workflow; entries describe the code and validation available in
the corresponding repository version.

## [0.4.0]

### Added

- Versioned external MCP runtime under `%LOCALAPPDATA%\OriginComAutomation\runtime\<version>`.
- Shared `mcp` schemas/helpers, COM worksheet/graph/project support modules, and deterministic
  hashing/runtime utilities.
- FigureSpec-to-WorkflowSpec adapter, project-input support, canonical task status, and one batch
  planner/executor.
- One graph catalog for typed, role-based, semilog, loglog, and multi-layer graph routes.

### Changed

- FigureSpec compatibility tools now execute through the same WorkflowEngine as WorkflowSpec.
- MCP launchers use a non-editable runtime instead of importing a copied repository `.venv`.
- File SHA-256, model digest, strict-model, and Origin-version logic now have one implementation.
- Public tool names, result envelopes, error codes, native-analysis defaults, and safety gates remain
  compatible with 0.3.1.

### Safety

- The external runtime is version-scoped and bootstrapped under a lock; attached Origin sessions
  remain read-only and only plugin-owned sessions may be shut down.

### Validation

- See [0.4.0 validation](docs/VALIDATION-0.4.0.md) for unit, static, distribution, stdio, and live
  Origin evidence.

### Known limits

- Specialized Origin versions and capability-gated graph/X-Function routes still require live
  verification on that installed Origin version.

## [0.3.1]

### Added

- Balanced fast `origin_run_task` execution with grouped missing scientific decisions.
- Automatic checkpoint policy: no checkpoint for ordinary work and one milestone for longer work.

### Changed

- Removed redundant ordinary-task audits, manifests, reopen checks, and worksheet scans.

### Safety

- Strict phase/mutation recovery remains opt-in and poisoned sessions are isolated.

### Validation

- See [0.3.1 validation](docs/VALIDATION-0.3.1.md).

### Known limits

- The 0.3.1 installer copied development runtime state; 0.4.0 replaces that path with an external
  immutable runtime.

## [0.3.0]

### Added

- Intent-aware WorkflowSpec, parameter contracts, native-first execution, stable refs, and
  reproducibility manifests.

### Changed

- Added strict plan, validate, execute, audit, and resume routes.

### Safety

- Non-overwriting project copies, fail-fast batches, and explicit source replacement gates.

### Validation

- See [0.3.0 validation](docs/VALIDATION-0.3.0.md).

### Known limits

- Strict workflow execution is more verbose than the balanced 0.3.1 route.

## [0.2.1]

### Added

- Native Origin formulas, analysis operations, connectors, templates, graph preview, and recovery.

### Changed

- Improved mixed-column import and write readback.

### Safety

- Added owned-process tracking and poisoned-session recovery.

### Validation

- See [0.2.1 validation](docs/VALIDATION-0.2.1.md).

### Known limits

- Origin installation and ProgID behavior remain version-dependent.

## [0.2.0]

### Added

- Initial structured Origin COM MCP surface for projects, worksheets, analyses, graphs, and exports.

### Changed

- Centralized COM access on a serial STA worker.

### Safety

- Source projects are protected by default.

### Validation

- See [0.2.0 validation](docs/VALIDATION-0.2.0.md).

### Known limits

- Only the verified Origin version matrix should be treated as supported.

## [0.1.0]

### Added

- First personal Codex plugin scaffold and local Python MCP server.

### Changed

- Established the plugin manifest, Skill, scripts, and test layout.

### Safety

- COM automation is local-only and explicit.

### Validation

- Initial unit and packaging checks.

### Known limits

- Feature coverage was limited to the first COM paths.
