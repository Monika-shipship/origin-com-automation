# Origin Automation 0.4 Architecture Consolidation Design

Status: approved scope under the user's autonomous two-release instruction

Release target: `origin-com-automation` 0.4.0

Baseline: locally verified 0.3.1

## Goal

Reduce duplicated implementations and installation bloat without removing public tools or changing
scientific behavior. Preserve every 0.3.1 safety boundary, native-analysis default, result schema,
and compatibility route while making one internal implementation authoritative per capability.

## Required Consolidations

1. Replace the copied editable repository `.venv` with a versioned external runtime. The launcher
   resolves the cached plugin root, creates `%LOCALAPPDATA%\OriginComAutomation\runtime\<version>`,
   and installs the current plugin non-editably. Installed code and metadata must match the cached
   manifest version, while test and type-check dependencies remain available through bootstrap.
2. Keep FigureSpec tools as compatibility APIs but convert FigureSpec to WorkflowSpec and execute
   it through WorkflowEngine. Extend WorkflowSpec to represent existing OPJU inputs so both legacy
   FigureSpec routes remain functional.
3. Make one TaskManager/status implementation and one batch planner/executor authoritative. Public
   status names remain aliases with their existing error codes.
4. Make `graphs.catalog` the sole graph-type registry. `create_plot` remains a typed compatibility
   adapter and `create_graph` remains the role-based interface; both use the same catalog entry.
5. Reduce `server.py` by extracting MCP schemas and shared tool helpers. Reduce `origin_api.py` by
   extracting cohesive pure graph, worksheet, and project support functions; retain OriginController
   as the public façade and do not change STA serialization or session ownership.
6. Consolidate file hashing, canonical model digests, strict Pydantic bases, and controller-version
   lookup into small shared utilities.

## Compatibility Boundary

No public MCP tool is removed. Existing inputs remain accepted. Existing output envelope fields and
error codes remain stable except where a previously stale package version is corrected. Source
projects remain non-overwriting by default, Python remains explicit-only, and attached sessions
remain read-only.

## Verification

Characterization tests must pass before and after each extraction. Add adapter equivalence tests,
runtime-location/version tests, catalog equivalence tests, task alias tests, and call-budget tests.
Run the complete unit suite, real stdio transport, package/plugin/Skill validators, and the same
bounded live Origin workflows used for 0.3.1. Record exact results in `VALIDATION-0.4.0.md`.

