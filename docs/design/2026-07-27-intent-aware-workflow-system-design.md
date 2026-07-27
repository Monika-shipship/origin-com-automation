# Intent-Aware Origin Workflow System Design

Status: approved direction, implementation planning pending

Release target: `origin-com-automation` 0.3.0

Baseline: `origin-com-automation` 0.2.1, Windows 11 x64, Python x64,
Origin 10.1.0.178

## 1. Goal

Evolve the plugin from a collection of COM tools into a workflow system that can:

- understand a declared analysis intent without inventing scientific choices;
- collect all missing scientific decisions before Origin is started;
- inspect source data and compile an immutable, digest-bound execution plan;
- execute the plan once through the existing controllers and serialized COM worker;
- stop at the first failed mutation and resume only from a durable checkpoint;
- verify Origin-native data, formulas, Analysis Operations, graphs, exports, and saves;
- deliver an editable OPJU project plus a reproducibility manifest.

Existing low-level MCP tools remain available. High-level workflows must call the same controller
methods as those tools so that safety, retry, ownership, and verification behavior cannot drift.

## 2. Chosen Architecture

Use an additive workflow coordination layer over the current controllers. Do not rewrite the COM
worker, session ownership model, connector controller, graph controller, or native-operation
registry. Generalize the existing FigureSpec plan-and-digest pattern into a WorkflowSpec kernel,
then adapt FigureSpec to that kernel.

The layers are:

1. Intent adapters for common tasks such as import-and-plot, curve analysis, fitting,
   multi-device comparison, statistics, and engineering figures.
2. A strict declarative WorkflowSpec shared by all high-level routes.
3. A scientific contract resolver that separates required decisions, derived facts, and safe
   engineering defaults.
4. An offline planner that inspects sources, validates capabilities, predicts mutations, assigns
   idempotency keys, and produces an immutable digest.
5. A serialized executor with a stage ledger and durable OPJU checkpoints.
6. Existing controller and COM layers.
7. Targeted validators and a reproducibility-manifest writer.

## 3. Public Interface

Add a small high-level surface instead of one new tool per workflow. The phase labels below are
part of the delivery boundary:

- P0, `origin_plan_workflow(spec)`: perform offline inspection and return the normalized spec,
  missing scientific decisions, blockers, warnings, mutation forecast, stages, capability status,
  idempotency keys, and plan digest. It must not activate Origin.
- P0, `origin_execute_workflow(spec, plan_digest, idempotency_key)`: reject any spec drift, submit the
  approved plan once, and return an execution ID immediately.
- P0, `origin_workflow_status(execution_id)`: return the stage ledger, current object, completed
  checkpoints, warnings, failure details, and artifacts.
- P1, `origin_resume_workflow(execution_id, plan_digest)`: reopen the latest durable checkpoint and
  continue at the first incomplete stage. It must never replay an already committed mutation.
- P1, `origin_audit_result(target, checks)`: perform a bounded audit of one worksheet, formula,
  operation, graph, export, or project rather than returning the full project tree.
- P2, `origin_export_manifest(execution_id, formats)`: write the verified manifest to an Origin Notes
  page and optionally JSON or text.

Existing FigureSpec tools remain compatible. Their planner and executor become adapters over the
shared workflow kernel after the kernel is proven.

## 4. WorkflowSpec Contract

WorkflowSpec contains:

- `intent`: one closed workflow intent plus an optional user description;
- `sources`: paths, sheets, expected hashes, import modes, and template policy;
- `data_contract`: header selection, row bounds, column roles, missing-value rules, filters, and
  normalization declarations;
- `scientific_contract`: branch, scan direction, model, fit method, derivative method, device and
  material parameters, units, physical definitions, and outlier policy;
- `steps`: formulas, transformations, native analyses, plots, and exports;
- `outputs`: project path, overwrite policy, exports, and manifest formats;
- `execution_policy`: native backend policy, fail-fast behavior, checkpoints, and idempotency;
- `qa_policy`: required data, formula, operation, graph, pixel, save, reopen, and shutdown checks.

Every scientific field is classified as one of:

- `provided`: explicitly supplied by the user;
- `derived`: deterministically inferred from inspected metadata and recorded with evidence;
- `required`: execution-blocking choice that the user must supply;
- `safe_default`: non-scientific operational behavior such as no overwrite or fail-fast.

Unit conversion may be derived when both source and requested units are explicit. A physical
definition, branch, derivative algorithm, fit model, outlier rule, or normalization basis must
never be guessed.

## 5. Origin-Native Expression Policy

The normal workflow should preserve Origin-native intent instead of expanding operations into
primitive arithmetic or materializing externally calculated values.

The expression planner chooses the first compatible, verified route in this order:

1. A verified Origin column function stored in Set Column Values `F(x)` metadata.
2. A verified X-Function that creates an Origin Analysis Operation with the requested
   recalculation mode.
3. The exact user-provided Origin formula.
4. An external backend only after explicit user selection.

The default backend policy is `origin_native_preferred`. This means a verified native route is
selected automatically, but absence of a compatible native route becomes a required decision. It
does not silently fall back to Python. `origin_native_only` and `external_explicit` remain
available for callers that need stricter behavior.

### Derivative example

Derivative remains a scientific choice. The contract must state the order, algorithm, input
range, branch, missing-value rule, and desired output/recalculation behavior.

- Use a verified `dderivative` column-function route when its installed Origin syntax and behavior
  match the requested derivative definition and the result should remain an editable column
  formula.
- Use the verified `differentiate` X-Function when the requested method matches its semantics and
  an Analysis Operation is the better editable representation.
- Do not substitute either route merely because it is native. If it changes point placement,
  boundary handling, smoothing, branch selection, or range semantics, planning must stop and show
  the difference as a required decision.
- Keep the current Python derivative only as an explicitly selected compatibility backend and
  mark it as non-native and non-recalculating in Origin.

Native selection should not reduce normal workflow efficiency. Capability resolution is cached by
Origin version, equivalent operations are grouped, and only risky or unverified formulas require
an Origin preview. The planner must not start Origin once per expression.

## 6. Formula Compatibility And Preview

Before submission, a formula analyzer performs bounded static checks:

- balanced parentheses and valid range references;
- allowlisted Origin function names and known cross-language naming differences;
- dynamic-index and row-bound risks;
- obvious division-by-zero, logarithm-domain, and square-root-domain risks;
- target-range validity and stale values outside the requested formula range;
- unsafe LabTalk delimiters or scripts.

Compatibility suggestions are advisory. The plugin may show a verified replacement but must not
rewrite a scientific formula without approval.

When an Origin-native preview is required, calculate representative rows in a plugin-owned
temporary column or worksheet, read the results back, and remove the temporary object. The preview
must report the exact expression, rows, inputs, outputs, warnings, and cleanup result.

## 7. Data Inspection And Import Modes

Offline inspection must detect or report:

- encoding, delimiter, decimal convention, scientific notation, and selected Excel sheet;
- leading explanation rows, header candidates, trailing empty rows, and effective data range;
- duplicate or blank labels, mixed columns, missing values, and representative head/tail rows;
- Unicode labels, long or spaced paths, source size, timestamp, and SHA-256;
- ambiguous header, decimal, or column-role decisions as blockers rather than guesses.

Import modes are explicit:

- `linked`: Origin remains connected to a regular source file and this is the default.
- `snapshot`: values are copied with no retained source connection.
- `normalized_linked`: the plugin creates a deterministic standardized file for an irregular
  source, links Origin to it, and records the original path, hash, transformation rules, and row
  mapping.

New workflows use a clean workbook and worksheet by default. Origin workbook templates are not
implicitly reused. Applying a template requires an explicit path/name, expected digest, compatible
layer or column structure, and post-application audit.

## 8. Plan, Ledger, And Recovery

The critical path is:

`inspect -> resolve_contract -> compile -> validate -> approve_digest -> start -> prepare_copy ->
import -> verify_data -> formula -> analysis -> plot -> export -> save -> reopen_audit -> manifest
-> shutdown`

The plan contains the expected objects, object aliases, formulas, operations, graphs, files,
capability statuses, verification checks, and mutation stages. Its digest covers all scientific and
operational fields.

Every mutating step has an idempotency key derived from the plan digest, step ID, target object,
and normalized arguments. The stage ledger stores expected and actual values, object refs,
artifacts, warnings, duration, and checkpoint path.

Batch and repeated operations default to `fail_fast=true`. On first failure, no later peer item is
executed. A resume opens the most recent plugin-owned checkpoint and starts with the first
uncommitted step. Mutating operations are not automatically retried. Read-only audits may use the
existing bounded transient-COM retry policy.

## 9. Stable Object References

Replace bare display names in high-level plans with structured ObjectRef records containing:

- object kind and session ID;
- plugin-generated logical ID;
- current Origin internal name and parent/container ref;
- long name and project-folder path as secondary fingerprints;
- aliases, generation, creation step, and verification state.

The session registry updates aliases when Origin renames an object. A targeted resolver searches by
logical ID and recorded fingerprints before accepting a renamed object. If Origin exposes no
persistent unique identifier, the reference is labeled `session_stable` or `rebindable`; it is not
described as permanently stable across arbitrary external edits.

## 10. Graph Layout And Pixel QA

The layout planner uses curve count, label length, graph dimensions, axis scale, and emphasis roles
to choose legend columns, font size, position, tick density, palette, symbols, and margins. Symbol
names are accepted only after their Origin code mapping is verified for the installed version.

PNG QA extends current nonblank/color metrics with edge-contact and content-margin thresholds,
extreme whitespace, expected dimensions, and suspected clipping. Text overlap remains a heuristic
warning unless Origin object geometry or a separately verified visual check proves it. The plugin
must not claim that all overlap is absent from pixel statistics alone.

## 11. Delivery Verification

A workflow succeeds only when all required checks pass:

- row count, critical columns, and representative values;
- connector identity, source hash, connected state, and refresh status;
- formula text, range, recalculation mode, and representative results;
- native operation identity, inputs, outputs, state, and recalculation mode;
- graph X/Y/label/category bindings, axes, units, and requested ranges;
- nonempty exports with required pixel checks;
- nonempty OPJU file, confirmed save state, and optional reopen audit;
- successful exit of the plugin-owned Origin instance without affecting user instances.

Results distinguish `verified`, `warning`, `unverified`, and `failed`. A required unverified check
prevents a success response.

## 12. Reproducibility Manifest

The final manifest records source paths and hashes, plugin and Origin versions, normalized user
parameters, required decisions, ranges, branches, filters, formulas, native functions,
X-Functions, fitting methods, units, warnings, assumptions, verification results, stable refs,
graphs, exports, project path, plan digest, and execution ID.

Write the manifest to a plugin-owned Origin Notes page and optionally JSON or text. Sensitive data
values are excluded; representative validation values are included only when the workflow contract
permits them.

## 13. Delivery Phases

### P0: workflow foundation

- WorkflowSpec and scientific parameter contract;
- enhanced offline source inspection and preview;
- immutable plan and mutation forecast;
- fail-fast execution, idempotency keys, and non-overwrite outputs;
- structured ObjectRef registry and targeted resolution;
- adapters over existing controllers with no duplicate COM behavior.

### P1: verified native execution and recovery

- native expression registry and planner, including verified derivative routes;
- formula static checks and bounded native preview;
- discontinuous ranges, branch/filter compilation, and plugin-owned helper ranges;
- durable stage ledger, OPJU checkpoints, and failed-stage resume;
- targeted worksheet, formula, operation, graph, and pixel audits;
- automatic legend/tick/margin planning within verified Origin mappings.

### P2: domain workflows and compatibility knowledge

- common curve, multi-device, fitting, statistics, and engineering-figure intents;
- reproducibility Notes and external manifest delivery;
- larger batch queues and reusable workflow templates;
- Origin-version capability and formula compatibility matrix;
- later domain adapters only after the shared contract is stable.

## 14. Acceptance Criteria

- Planning detects all missing scientific choices in one response and performs no COM activation.
- An approved digest executes through existing controllers without a second implementation path.
- Supported derivative and fitting requests create verified Origin-native formulas or Analysis
  Operations and remain editable and recalculating after save/reopen.
- Unsupported native semantics block or require explicit external-backend approval; no silent
  substitution occurs.
- Batch execution stops at the first failure and resume does not duplicate completed objects.
- Renamed objects remain resolvable when their structured fingerprints are sufficient; ambiguous
  rebinding fails closed.
- Required delivery checks cover data, connectors, formulas, operations, graph bindings, pixels,
  project save/reopen, and owned-instance shutdown.
- The final OPJU and manifest explain exactly what was requested, executed, verified, warned, and
  left unverified.

## 15. Quality Metrics

Track workflow quality using first-run success rate, mean correction count, required-check
coverage, native/editable result rate, resume success rate, and scientific-decision transparency.
Raw COM call success remains diagnostic data, not the primary product-quality metric.

## 16. Release Documentation

The 0.3.0 release adds a repository-level `CHANGELOG.md`. It documents 0.1.0, 0.2.0, 0.2.1,
and 0.3.0 in release order. Each entry distinguishes added behavior, changed defaults, safety or
verification improvements, live-verified scope, and known limitations. README summaries link to
the changelog instead of duplicating the complete release history.
