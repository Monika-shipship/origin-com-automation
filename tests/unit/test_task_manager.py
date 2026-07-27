import threading
import time

import pytest

from origin_com_automation.workflows.tasks import TaskManager


def wait_terminal(manager, task_id, timeout=2):
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = manager.status(task_id)
        if state["state"] in {"succeeded", "failed", "cancelled"}:
            return state
        time.sleep(0.01)
    raise AssertionError("task did not finish")


def test_task_manager_reports_monotonic_stages_and_success():
    manager = TaskManager(max_results=10)

    def work(context):
        context.stage("preflight")
        context.stage("input")
        return {"ok": True}

    task_id = manager.submit("figure", work)
    state = wait_terminal(manager, task_id)
    assert state["state"] == "succeeded"
    assert state["completed_stages"] == ["preflight", "input"]
    assert state["result"] == {"ok": True}
    manager.shutdown()


def test_pending_task_can_cancel_but_running_mutation_cannot():
    manager = TaskManager(max_results=10)
    release = threading.Event()

    def blocking(context):
        context.stage("mutation", mutation=True)
        release.wait(1)
        return {"done": True}

    first = manager.submit("first", blocking)
    deadline = time.time() + 1
    while manager.status(first)["state"] != "running" and time.time() < deadline:
        time.sleep(0.01)
    second = manager.submit("second", lambda context: {})
    cancelled = manager.cancel(second)
    unsafe = manager.cancel(first)
    assert cancelled["state"] == "cancelled"
    assert unsafe["error_code"] == "TASK_CANCEL_NOT_SAFE"
    release.set()
    wait_terminal(manager, first)
    manager.shutdown()


def test_task_manager_retention_is_bounded():
    manager = TaskManager(max_results=2)
    ids = [manager.submit(str(index), lambda context, index=index: index) for index in range(3)]
    for task_id in ids:
        try:
            wait_terminal(manager, task_id)
        except KeyError:
            pass
    assert manager.task_count <= 2
    manager.shutdown()


def test_idempotency_key_returns_original_task_and_runs_once():
    manager = TaskManager(max_results=10)
    calls = []

    def work(context):
        calls.append("run")
        return {"ok": True}

    first = manager.submit("workflow", work, idempotency_key="approved-plan")
    second = manager.submit("workflow", work, idempotency_key="approved-plan")

    assert second == first
    assert wait_terminal(manager, first)["state"] == "succeeded"
    assert calls == ["run"]
    with pytest.raises(ValueError, match="different task"):
        manager.submit("other", work, idempotency_key="approved-plan")
    manager.shutdown()


def test_stage_ledger_records_expected_actual_object_and_mutation_key():
    manager = TaskManager(max_results=10)

    def work(context):
        context.stage(
            "import",
            mutation=True,
            idempotency_key="mutation:import",
            object_ref="worksheet:data",
            expected={"rows": 2},
        )
        context.complete_stage(actual={"rows": 2})
        context.stage("audit", mutation=False, object_ref="worksheet:data")
        context.complete_stage(actual={"verified": True})
        return {"ok": True}

    task_id = manager.submit("workflow", work)
    state = wait_terminal(manager, task_id)

    assert state["completed_stages"] == ["import", "audit"]
    assert state["completed_mutation_keys"] == ["mutation:import"]
    assert state["stage_events"][0] == {
        "stage_id": "import",
        "state": "completed",
        "mutation": True,
        "idempotency_key": "mutation:import",
        "object_ref": "worksheet:data",
        "expected": {"rows": 2},
        "actual": {"rows": 2},
        "error_code": None,
        "error_message": None,
    }
    manager.shutdown()


def test_completed_mutation_key_cannot_be_replayed_in_same_task():
    manager = TaskManager(max_results=10)

    def work(context):
        context.stage("write", mutation=True, idempotency_key="mutation:write")
        context.complete_stage(actual={"written": True})
        context.stage("write-again", mutation=True, idempotency_key="mutation:write")

    task_id = manager.submit("workflow", work)
    state = wait_terminal(manager, task_id)

    assert state["state"] == "failed"
    assert state["error_code"] == "MUTATION_ALREADY_COMPLETED"
    manager.shutdown()
