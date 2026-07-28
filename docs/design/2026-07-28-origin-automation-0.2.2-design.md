# Origin COM Automation 0.2.2 Maintenance Design

Status: approved

Release target: `origin-com-automation` 0.2.2

Baseline: `v0.2.1` on `rollback/v0.2.1`

## Goal

Apply the behavior-neutral engineering improvements identified during the 0.4 work to the lean
0.2.1 plugin. Improve installation reliability and internal maintainability without adding tools,
workflow stages, scientific capabilities, validation passes, or user-visible task steps.

Accuracy and successful completion remain the first priorities. Runtime behavior must remain as
direct as 0.2.1: ask only for missing scientific decisions, use linked imports by default, prefer
Origin-native formulas and Analysis Operations, execute the requested work once, and perform only
the existing bounded verification.

## Public Compatibility Contract

0.2.2 preserves the complete 0.2.1 public surface:

- Exactly 45 MCP tools.
- Identical tool names, input schemas, defaults, output envelopes, and error codes.
- Identical FigureSpec and focused-tool execution paths.
- Identical linked-import defaults and Origin-native formula and analysis behavior.
- Identical session ownership, timeout, recovery, non-overwrite, and shutdown safeguards.
- Identical task step count and user-visible decision flow.

Schema snapshots and characterization tests will guard this contract. A refactor that requires a
public compatibility exception is out of scope for 0.2.2.

## Included Changes

### 1. Versioned external runtime

Replace the plugin-local copied `.venv` runtime with a runtime stored under
`%LOCALAPPDATA%\OriginComAutomation\runtime\<plugin-version>`. The MCP launcher resolves the version
from the plugin manifest, creates the environment when missing, and runs the installed 0.2.2
package from that environment.

Bootstrap uses an exclusive file lock so concurrent Codex launches cannot corrupt the runtime.
Installation is non-editable, runtime metadata records the installed plugin version, and local test
dependencies remain an explicit bootstrap option. This changes packaging only; it does not add an
MCP call or an Origin workflow stage.

### 2. Focused MCP modules

Move MCP request models, schema expansion, and response/helper functions out of `server.py` into
focused `mcp` modules. `server.py` remains the registration and dispatch layer. Existing model names
remain importable where tests or internal callers rely on them.

No tool registration, parameter schema, default, timeout, return envelope, or dispatch target may
change during this extraction.

### 3. Focused COM support modules

Move cohesive pure worksheet, graph, and project helper functions out of `com/origin_api.py` into
support modules. `OriginController` remains the public facade and retains the same method signatures,
STA worker serialization, session state, ownership checks, retry rules, and timeout behavior.

Only stateless or narrowly scoped helper code is eligible for extraction. COM lifecycle and stateful
controller logic stay in their existing authoritative classes.

### 4. Shared internal utilities

Consolidate duplicated file hashing, canonical digest, and controller-version lookup helpers into
small shared utility modules. Historical digest values and result fields must remain unchanged.

## Explicitly Excluded

The following 0.3 and 0.4 capabilities will not be added or used:

- WorkflowSpec, WorkflowEngine, workflow adapters, or `origin_run_task`.
- Planning approvals, immutable digests, ledgers, manifests, or checkpoints.
- Additional recovery points or verification stages.
- New MCP tools, schemas, graph types, analyses, formulas, or object models.
- FigureSpec conversion through a workflow engine.
- Changes to the Skill that make routine tasks longer or more conversational.

The 0.4 graph-catalog, task-manager, workflow, expression, reference, and audit expansions are also
excluded because they either depend on later workflow architecture or extend behavior beyond 0.2.1.

## Execution Flow

The user-visible path remains:

1. Resolve the existing focused tool or FigureSpec route.
2. Ask once only when a required scientific parameter is absent.
3. Start or use the safely owned Origin session.
4. Import linked data or open the protected working copy.
5. Execute Origin-native formulas or Analysis Operations where supported.
6. Create or update the requested graph and export artifacts.
7. Run the existing bounded result checks and close owned resources.

External runtime bootstrapping happens before MCP startup and is not part of an Origin task.

## Error Handling

Bootstrap failures must fail clearly before starting the MCP server and must not leave a partially
reported successful runtime. Lock acquisition is bounded. Runtime metadata is written only after a
successful package installation.

Internal module extraction must preserve all 0.2.1 exception translation and error codes. No new
retry loop, recovery checkpoint, or validation retry is introduced.

## Testing Strategy

Implementation uses characterization-first tests:

1. Capture the 0.2.1 tool count, names, and JSON schemas before extraction.
2. Add failing packaging tests for the external versioned runtime, launcher, lock, and non-editable
   install contract.
3. Add focused import and equivalence tests before moving MCP and COM helpers.
4. Run the complete unit suite after each extraction.
5. Validate real stdio MCP transport and the plugin manifest.
6. Run the existing bounded live Origin 0.2.1 smoke workflow, including linked data, `F(x)`, native
   analysis, save/reopen, graph export/QA, connector refresh, and owned shutdown when Origin is
   available.

Success requires no tool or schema drift, no additional Origin calls in characterized routes, no
new user-visible stages, and no regression in the live smoke workflow. Simulated tests will never
be reported as proof of real COM success.

## Delivery

Update all version sources to 0.2.2, add bilingual release notes, build and validate the package,
refresh the local Codex plugin cachebuster, and install the local 0.2.2 plugin. Work remains local:
no push, tag, or GitHub release is created unless requested separately.
