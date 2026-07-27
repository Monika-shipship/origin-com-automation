# Balanced Fast Workflow Design

Status: approved direction, written specification pending user review

Release target: `origin-com-automation` 0.3.1

Baseline: `origin-com-automation` 0.3.0, Windows 11 x64, Python x64,
Origin 10.1.0.178

## 1. Goal

Make successful completion of the requested Origin task the primary metric while removing
execution work that does not materially improve correctness. A user who supplies complete data
and scientific requirements should normally receive the finished editable project and requested
exports from one high-level call. The plugin asks questions only when a missing value changes the
scientific meaning of the result or authorizes a destructive action.

The redesign preserves the 0.3.0 strengths: source projects are not overwritten by default,
linked imports remain linked, calculations stay in Origin, native Analysis Operations are
preferred, mutations fail fast, critical values are read back, graph bindings are checked, and
only plugin-owned Origin instances are closed.

## 2. Chosen Approach

Add an adaptive synchronous fast path over the existing WorkflowSpec engine. Keep the existing
plan, execute, status, resume, audit, and manifest tools for advanced use, but stop routing ordinary
tasks through that entire public sequence.

The alternatives were rejected as follows:

- returning to the 0.2.1 controller sequence would be fast but would discard useful stable refs,
  scientific contracts, and native-expression planning;
- retaining the current 0.3.0 phase workflow and only tuning individual calls would leave repeated
  OPJU saves and redundant verification in the common path.

## 3. Public Entry Point

Add `origin_run_task(spec)` as the preferred complete-task entry point.

It performs an in-process preflight and then follows one of two outcomes:

1. If scientific decisions are missing, return all of them together without starting Origin.
2. If the contract is complete, execute synchronously and return the final result, methods,
   stable refs, artifacts, decisive verification, warnings, and shutdown state.

The caller does not supply a digest, idempotency key, task ID, or polling loop for an ordinary
task. The engine may create those internally for traceability. Existing asynchronous tools remain
available for batches, unattended jobs, explicit resume, and advanced debugging.

## 4. Scientific Question Boundary

Ask only for unresolved choices that can change the scientific conclusion, including an exact
data range or branch, fit model and constraints, derivative or smoothing method, filter and
outlier policy, physical definition, normalization basis, and required units.

Do not ask the user to choose workbook names, temporary locations, stable IDs, connector options,
safe output names, graph page names, cache paths, retry counts, recovery profiles, or other routine
engineering details. Resolve those deterministically.

## 5. Recovery Policies

Extend the existing checkpoint policy without removing backward compatibility:

- `auto`, default: select milestone recovery when the plan has at least two sources, at least
  three native-analysis invocations, at least 100 MiB of local source data plus an analysis, or at
  least three independent batch items; use no checkpoint otherwise;
- `none`: never create an intermediate OPJU; save only the final requested project;
- `milestone`: create at most one checkpoint for a non-batch workflow and at most two for a batch;
- `phase`: retain the 0.3.0 phase checkpoints when the user explicitly requests strict recovery;
- `mutation`: retain the strongest diagnostic mode as an explicit advanced option.

Milestone candidates are limited to:

1. after all data sources and calculated columns are ready, but only when multiple or expensive
   analyses still remain;
2. after all native analyses are complete, when at least one plot or export remains.

A non-batch workflow creates no more than one of those candidates: prefer the data milestone when
multiple/large sources triggered recovery, otherwise use the analysis milestone. A batch may keep
at most two verified milestones across its item groups.

No checkpoint is created after an individual formula, individual analysis, graph, manifest, or
export. The final project save is not duplicated by another checkpoint. In-memory progress is
written to the ledger only at a checkpoint, failure, and final completion instead of after every
successful stage.

## 6. Fast Execution Path

For a typical one-source, one-analysis, one-graph task, the target path is:

1. one health/start sequence for a fresh owned Origin instance;
2. one linked import or one working-copy open;
3. reuse the import/write tool's verified column profiles and returned stable worksheet ref;
4. one exact Origin-native formula or Analysis Operation;
5. one graph creation and one combined configuration call;
6. one final OPJU save and one export per requested artifact;
7. decisive final validation and one owned-session shutdown.

The default path has zero intermediate OPJU saves, no default Notes or JSON manifest, no project
reopen, no whole-project object-tree audit after graph creation, no full worksheet reread when the
import already returned sufficient verified profiles, and no asynchronous status polling.

## 7. Necessary Verification

The fast path must still fail unless these result-defining checks succeed:

- source path, selected sheet/header, row count, critical X/Y columns, and representative values;
- linked connector state when linked import was requested;
- worksheet writes and formulas through the controller's immediate bounded readback;
- exact native analysis method, source range, output refs, operation presence, and recalculation
  mode;
- graph X/Y/label/category bindings and requested axis type;
- saved OPJU and exported files exist, are nonempty, and match their requested formats;
- a PNG export is nonblank and not obviously clipped when visual export is requested;
- a plugin-owned Origin instance exits, while attached or pre-existing user sessions remain open.

Do not repeat a successful check at a higher layer. Reopen the final project only when the user
requests persistence proof, a source replacement is authorized, or a version-sensitive operation
cannot otherwise be verified reliably.

## 8. Manifest And Audit Behavior

Default `manifest_formats` to an empty list. The normal result envelope contains a compact method
and verification receipt without creating extra files or an Origin Notes page.

Generate a reproducibility manifest only when requested, for publication delivery, or for an
explicit strict/unattended workflow. Use targeted audits for returned refs; never call
`list_objects` merely for reassurance after a successful mutation.

## 9. Failure Behavior

Remain fail-fast. Idempotent reads may use the controller's bounded retry. Writes, formulas,
analyses, saves, and exports are never replayed blindly. A known lookup mismatch may trigger one
targeted ref refresh and one correction. A first COM timeout abandons the poisoned worker; resume
is offered only when a verified milestone or strict checkpoint exists. Otherwise the owned
working session is closed or abandoned safely and the source remains untouched.

## 10. Compatibility

All 0.3.0 low-level and strict workflow tools remain available. Existing explicit `none`, `phase`,
and `mutation` policies keep their meaning. Native Origin remains the default backend; Python runs
only under an explicit external policy. No source overwrite behavior is relaxed.

## 11. Verification And Acceptance

Unit tests with fake controllers must assert the actual call budget, not only successful envelopes:

- a complete ordinary task uses one high-level call, one final project save, zero checkpoints,
  zero default manifests, zero reopen operations, and no redundant full-object or full-sheet read;
- missing scientific parameters return together before controller creation or Origin startup;
- milestone mode creates no more than its one/two-checkpoint budget and resumes without replaying
  completed mutations;
- explicit phase and mutation policies retain their 0.3.0 behavior;
- all critical data, native-operation, graph-binding, artifact, and shutdown checks still run;
- existing 0.3.0 tool schemas remain compatible.

The live Origin smoke test must cover the complete fast path with linked data, an Origin-native
operation, an editable graph, one OPJU save, one export, decisive verification, and owned-process
exit. A separate milestone smoke test should prove resume only when it can be interrupted safely;
until then milestone resume remains supported-unverified.

## 12. Documentation And Release

Release as 0.3.1. Update both READMEs, the Skill critical path, capability descriptions,
CHANGELOG, version metadata, and a `VALIDATION-0.3.1.md` report. The documentation must present
`origin_run_task` as the normal route and strict workflow tools as opt-in advanced controls.
