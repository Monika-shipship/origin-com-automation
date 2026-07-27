# Origin Automation 0.4 Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate six identified architecture and packaging duplications while preserving the complete 0.3.1 public behavior.

**Architecture:** Keep public MCP compatibility façades and replace duplicate internals with shared utilities, adapters, catalogs, and registrars. Use characterization-first extraction so COM/session behavior cannot drift.

**Tech Stack:** Python 3.13, PowerShell, Pydantic 2, FastMCP, pywin32 COM, pytest, Ruff, mypy.

---

### Task 1: Versioned immutable runtime

**Files:**
- Create: `scripts/run_mcp.ps1`
- Create: `scripts/runtime_path.ps1`
- Modify: `scripts/bootstrap.ps1`
- Modify: `scripts/diagnose.ps1`
- Modify: `.mcp.json`
- Test: `tests/unit/test_distribution_validation.py`

- [ ] Add failing tests requiring an external versioned runtime, a non-editable installation, and a launcher that imports code from the cached plugin version.
- [ ] Implement the version resolver and concurrency-safe bootstrap under `%LOCALAPPDATA%\OriginComAutomation\runtime\<manifest-version>`.
- [ ] Make `.mcp.json` call the launcher; keep test extras in bootstrap and runtime-only dependencies in first MCP launch.
- [ ] Prove package metadata and `origin_com_automation.__file__` no longer point to the source checkout; commit.

### Task 2: Shared workflow contracts and FigureSpec adapter

**Files:**
- Create: `src/origin_com_automation/workflows/models.py`
- Create: `src/origin_com_automation/workflows/adapters.py`
- Modify: `workflows/spec.py`
- Modify: `workflows/figurespec.py`
- Modify: `workflows/executor.py`
- Modify: `workflows/planner.py`
- Modify: `workflows/engine.py`
- Test: `tests/unit/test_figurespec.py`
- Test: `tests/unit/test_workflow_engine.py`

- [ ] Add characterization tests comparing FigureSpec plans/results with equivalent WorkflowSpecs for data-to-project and restyle-project routes.
- [ ] Move StrictModel and shared output/plot concepts to `models.py` without schema drift.
- [ ] Add OPJU source/open-working-copy support to WorkflowSpec and convert FigureSpec through `adapters.py`.
- [ ] Make the legacy executor delegate to WorkflowEngine and retain legacy result keys/error codes; commit.

### Task 3: Unified tasks and batches

**Files:**
- Modify: `src/origin_com_automation/workflows/tasks.py`
- Modify: `src/origin_com_automation/workflows/batch.py`
- Modify: `src/origin_com_automation/server.py`
- Test: `tests/unit/test_task_manager.py`
- Test: `tests/unit/test_batch_workflow.py`
- Test: `tests/unit/test_server_tools.py`

- [ ] Add failing tests proving both status tools read one record and server batch execution uses `build_batch_plan`/`execute_batch`.
- [ ] Add one internal status helper with public error-code aliases and route production batches through the tested batch module.
- [ ] Preserve serial fail-fast behavior, item ordering, and cancellation safety; commit.

### Task 4: One graph catalog and execution kernel

**Files:**
- Modify: `src/origin_com_automation/graphs/catalog.py`
- Modify: `src/origin_com_automation/services/graphs.py`
- Modify: `src/origin_com_automation/com/origin_api.py`
- Test: `tests/unit/test_graph_catalog.py`
- Test: `tests/unit/test_plot_controller.py`

- [ ] Add failing equivalence tests for scatter, line, line-symbol, bar, semilog, loglog, and multi-layer through both graph entry points.
- [ ] Move every typed graph definition to `graphs.catalog`; make `build_graph_spec` consume catalog metadata.
- [ ] Keep `create_plot` as the typed adapter and `create_graph` as the role adapter over the same execution kernel; commit.

### Task 5: Split MCP server and COM support modules

**Files:**
- Create: `src/origin_com_automation/mcp/__init__.py`
- Create: `src/origin_com_automation/mcp/schemas.py`
- Create: `src/origin_com_automation/mcp/helpers.py`
- Create: `src/origin_com_automation/com/worksheet_support.py`
- Create: `src/origin_com_automation/com/graph_support.py`
- Create: `src/origin_com_automation/com/project_support.py`
- Modify: `src/origin_com_automation/server.py`
- Modify: `src/origin_com_automation/com/origin_api.py`
- Test: `tests/unit/test_server_tools.py`
- Test: `tests/unit/test_origin_api.py`
- Test: `tests/unit/test_feedback_regressions.py`

- [ ] Add/import characterization tests for all extracted private helpers and full MCP schemas.
- [ ] Move Pydantic tool models and schema expansion to `mcp/`; preserve exported names temporarily.
- [ ] Move pure worksheet, graph, and project helper groups to support modules; re-export imported names from `origin_api.py` for test compatibility.
- [ ] Confirm OriginController, serialization decorator, ownership state, and public method signatures remain unchanged; commit.

### Task 6: Shared utilities

**Files:**
- Create: `src/origin_com_automation/utils/__init__.py`
- Create: `src/origin_com_automation/utils/hashing.py`
- Create: `src/origin_com_automation/utils/runtime.py`
- Modify: hashing/model/server call sites
- Test: `tests/unit/test_services.py`
- Test: `tests/unit/test_release_audit.py`

- [ ] Add failing tests for streaming file hashes, canonical model digests, and controller-version lookup.
- [ ] Replace duplicated SHA-256 and version lookup helpers without changing digest values.
- [ ] Remove dead duplicate helpers and prove all historical digest fixtures remain stable; commit.

### Task 7: 0.4 documentation, validation, and local release

**Files:**
- Modify: both READMEs, Skill, CHANGELOG, version sources, architecture docs
- Create: `docs/VALIDATION-0.4.0.md`

- [ ] Set 0.4.0 versions and cachebuster, document compatibility façades and external runtime, and update bilingual content tests.
- [ ] Run the full unit/static/build/distribution/plugin/Skill gates and bounded live Origin smoke suite.
- [ ] Measure source/runtime/cache sizes, verify non-editable installed metadata, tool count, stdio calls, and preservation of the existing Origin process.
- [ ] Fast-forward local `main`, install 0.4.0 locally, record exact evidence, and commit without pushing or tagging.
