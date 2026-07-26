import threading
import time

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

