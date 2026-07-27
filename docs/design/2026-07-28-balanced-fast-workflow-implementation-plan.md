# Balanced Fast Workflow 0.3.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver ordinary Origin tasks through one synchronous, accurate call with zero default checkpoints and retain bounded milestone/strict recovery for long tasks.

**Architecture:** Add `origin_run_task` over WorkflowEngine, resolve recovery policy during planning, and make verification reuse controller evidence. Preserve all existing strict workflow tools and native Origin defaults.

**Tech Stack:** Python 3.13, Pydantic 2, FastMCP, pywin32 COM, pytest, Ruff, mypy.

---

### Task 1: Fast defaults and recovery policy

**Files:**
- Modify: `src/origin_com_automation/workflows/spec.py`
- Modify: `src/origin_com_automation/workflows/planner.py`
- Test: `tests/unit/test_workflow_spec.py`
- Test: `tests/unit/test_workflow_planner.py`

- [ ] Add failing tests asserting empty default manifests, `reopen_project=false`, and `checkpoint_policy=auto`.
- [ ] Add failing planner tests for deterministic `none` versus `milestone` selection, including the source-count, analysis-count, 100 MiB, and batch-count thresholds.
- [ ] Extend the checkpoint literal with `auto` and `milestone`; change only the new defaults while retaining `none`, `phase`, and `mutation`.
- [ ] Return `resolved_checkpoint_policy` and `milestone_after` in the compiled plan.
- [ ] Run `pytest tests/unit/test_workflow_spec.py tests/unit/test_workflow_planner.py -q` and commit.

### Task 2: Lean synchronous engine execution

**Files:**
- Modify: `src/origin_com_automation/workflows/engine.py`
- Test: `tests/unit/test_workflow_engine.py`

- [ ] Add a call-counting fake-controller test for one source, one analysis, one graph: one save, no checkpoint, no manifest, no reopen audit, no redundant `list_objects`, and no redundant full worksheet read.
- [ ] Add milestone tests proving one non-batch checkpoint, no plot/manifest checkpoint, and no replay during resume.
- [ ] Make stages conditional on requested manifests and reopen QA; persist ledgers only at failure, checkpoint, and completion for `none`/`milestone`.
- [ ] Reuse verified `import_data` profiles and stable refs; perform a targeted read only when required critical evidence is absent.
- [ ] Remove the post-create full object audit and implement bounded final evidence in the returned execution receipt.
- [ ] Run `pytest tests/unit/test_workflow_engine.py -q` and commit.

### Task 3: One-call MCP entry

**Files:**
- Modify: `src/origin_com_automation/server.py`
- Test: `tests/unit/test_server_tools.py`
- Test: `tests/unit/test_mcp_transport.py`

- [ ] Add failing schema and behavior tests for `origin_run_task(spec)`, including preflight-only return before controller creation when scientific decisions are missing.
- [ ] Implement synchronous planning and execution with an internal digest/idempotency key and the standard ResultEnvelope.
- [ ] Preserve the fresh-controller boundary and return `needs_input`, final methods, stable refs, artifacts, verification, warnings, and shutdown state.
- [ ] Verify 52 tools and real stdio planning/execution schema discovery; commit.

### Task 4: Skill, documentation, release metadata

**Files:**
- Modify: `skills/origin-automation/SKILL.md`
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `CHANGELOG.md`
- Modify: `.codex-plugin/plugin.json`
- Modify: `pyproject.toml`
- Modify: `src/origin_com_automation/__init__.py`
- Create: `docs/VALIDATION-0.3.1.md`
- Test: `tests/unit/test_readme_content.py`
- Test: `tests/unit/test_skill_content.py`
- Test: `tests/unit/test_release_audit.py`

- [ ] Add failing content/version tests requiring the one-call default route and strict recovery opt-in wording.
- [ ] Update English and Chinese documentation consistently, add 0.3.1 changelog notes, and set all version sources to 0.3.1 with a plugin cachebuster.
- [ ] Validate the Skill and plugin manifests; commit.

### Task 5: Complete verification and local release

- [ ] Run the full unit suite, Ruff, mypy, build, pip check, release audit, distribution validator, official plugin validator, and Skill validator.
- [ ] Run live Origin smoke tests with explicit preservation of the pre-existing Origin process.
- [ ] Fast-forward local `main`, reinstall from the personal marketplace, and verify installed version, 52 tools, health, capabilities, and offline/complete fast-task stdio calls.
- [ ] Add exact evidence to `VALIDATION-0.3.1.md` and commit without pushing or tagging.

