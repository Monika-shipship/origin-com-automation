# Bilingual README And 0.2 Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish `v0.2.0` before `v0.2.1` and provide synchronized, detailed English and
Simplified Chinese repository documentation.

**Architecture:** Keep `README.md` as the English source and add `README.zh-CN.md` with the same
major section order, capability boundaries, commands, architecture flow, and disclaimer. Release
tags point to immutable verified commits while `main` advances in the same order.

**Tech Stack:** Markdown, Mermaid, PowerShell, Git, Codex plugin validators, pytest.

---

### Task 1: Publish The Existing 0.2.0 Commit

**Files:**
- No file changes

- [ ] **Step 1: Verify the release boundary**

Run:

```powershell
git merge-base --is-ancestor main 8fdbf68
git show --no-patch --oneline 8fdbf68
git ls-remote --tags origin
```

Expected: `8fdbf68` is a descendant of local `main`, and remote `v0.2.0` is absent.

- [ ] **Step 2: Fast-forward and tag 0.2.0**

```powershell
git switch main
git merge --ff-only 8fdbf68
git tag -a v0.2.0 8fdbf68 -m "Origin COM Automation 0.2.0"
```

- [ ] **Step 3: Push and verify 0.2.0**

```powershell
git push origin main
git push origin v0.2.0
git ls-remote origin refs/heads/main refs/tags/v0.2.0 refs/tags/v0.2.0^{}
```

Expected: remote `main` and dereferenced `v0.2.0` both resolve to `8fdbf68`.

### Task 2: Add Synchronized English And Chinese Documentation

**Files:**
- Modify: `README.md`
- Create: `README.zh-CN.md`
- Test: `tests/unit/test_readme_content.py`

- [ ] **Step 1: Add failing documentation contract tests**

Require both README files to contain matching ordered section identifiers, mutual language links,
the Mermaid architecture nodes, the default linked/native/formula policies, both validation
report links, the independent-project disclaimer, backup/output-review warnings, and MIT terms.

- [ ] **Step 2: Run the tests and verify RED**

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests\unit\test_readme_content.py -q
```

Expected: failure because `README.zh-CN.md` and the new English sections do not exist.

- [ ] **Step 3: Write the synchronized README files**

Keep the same major section order and factual scope. Use concise English in `README.md`; explain
the same concepts in accessible Simplified Chinese in `README.zh-CN.md`. Include a shared Mermaid
flow covering Codex, MCP, controller, STA, Origin native interfaces, and verified artifacts.

- [ ] **Step 4: Run the documentation tests and verify GREEN**

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests\unit\test_readme_content.py -q
```

Expected: all documentation contract tests pass.

### Task 3: Validate And Commit 0.2.1 Documentation

**Files:**
- Modify: `README.md`
- Create: `README.zh-CN.md`
- Create: `tests/unit/test_readme_content.py`

- [ ] **Step 1: Run complete local gates**

```powershell
& '.\.venv\Scripts\python.exe' -m compileall -q src tests
& '.\.venv\Scripts\python.exe' -m pytest tests\unit -q -p no:faulthandler
& '.\.venv\Scripts\python.exe' -m ruff check .
& '.\.venv\Scripts\python.exe' -m mypy
& '.\.venv\Scripts\python.exe' -m build
& '.\.venv\Scripts\python.exe' -m pip check
& '.\.venv\Scripts\python.exe' scripts\release_audit.py .
& '.\.venv\Scripts\python.exe' scripts\validate_distribution.py .
```

Also run the official plugin and Skill validators. Require zero failures.

- [ ] **Step 2: Commit the documentation release**

```powershell
git add README.md README.zh-CN.md tests/unit/test_readme_content.py
git commit -m "Add synchronized Chinese plugin documentation"
```

### Task 4: Publish And Verify 0.2.1

**Files:**
- No file changes

- [ ] **Step 1: Fast-forward main and create the tag**

```powershell
git switch main
git merge --ff-only feature/v0.2-expansion
git tag -a v0.2.1 HEAD -m "Origin COM Automation 0.2.1"
```

- [ ] **Step 2: Push in order and verify remote refs**

```powershell
git push origin main
git push origin v0.2.1
git ls-remote origin refs/heads/main refs/tags/v0.2.0^{} refs/tags/v0.2.1^{}
```

Expected: remote `v0.2.0` remains at `8fdbf68`; remote `main` and dereferenced `v0.2.1` resolve to
the final bilingual documentation commit.
