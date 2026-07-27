"""One serialized background task queue with stage progress."""

from __future__ import annotations

import time
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
from threading import RLock
from typing import Any, Callable
from uuid import uuid4


class MutationAlreadyCompleted(RuntimeError):
    code = "MUTATION_ALREADY_COMPLETED"


class TaskContext:
    def __init__(self, manager: "TaskManager", task_id: str) -> None:
        self._manager = manager
        self.task_id = task_id

    def stage(
        self,
        stage_id: str,
        *,
        mutation: bool = False,
        idempotency_key: str | None = None,
        object_ref: str | None = None,
        expected: Any = None,
    ) -> None:
        self._manager._stage(
            self.task_id,
            stage_id,
            mutation=mutation,
            idempotency_key=idempotency_key,
            object_ref=object_ref,
            expected=expected,
        )

    def complete_stage(self, *, actual: Any = None) -> None:
        self._manager._complete_stage(self.task_id, actual=actual)

    def fail_stage(
        self,
        error_code: str,
        error_message: str,
        *,
        actual: Any = None,
    ) -> None:
        self._manager._fail_stage(
            self.task_id,
            error_code=error_code,
            error_message=error_message,
            actual=actual,
        )


class TaskManager:
    def __init__(self, *, max_results: int = 100) -> None:
        if max_results < 1:
            raise ValueError("max_results must be positive")
        self.max_results = max_results
        self._lock = RLock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="origin-workflow")
        self._tasks: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._idempotency: dict[str, tuple[str, str]] = {}

    @property
    def task_count(self) -> int:
        with self._lock:
            return len(self._tasks)

    def submit(
        self,
        name: str,
        function: Callable[[TaskContext], Any],
        *,
        idempotency_key: str | None = None,
    ) -> str:
        normalized_key = idempotency_key.strip() if idempotency_key else None
        with self._lock:
            if normalized_key and normalized_key in self._idempotency:
                existing_name, existing_id = self._idempotency[normalized_key]
                if existing_name != name:
                    raise ValueError(
                        "idempotency key is already bound to a different task"
                    )
                return existing_id
        task_id = uuid4().hex
        record: dict[str, Any] = {
            "task_id": task_id,
            "name": name,
            "state": "queued",
            "current_stage": None,
            "completed_stages": [],
            "stage_events": [],
            "completed_mutation_keys": [],
            "mutation_active": False,
            "idempotency_key": normalized_key,
            "result": None,
            "error_code": None,
            "error_message": None,
            "created_at": time.time(),
            "started_at": None,
            "finished_at": None,
            "future": None,
        }
        with self._lock:
            self._tasks[task_id] = record
            if normalized_key:
                self._idempotency[normalized_key] = (name, task_id)

        def run() -> Any:
            with self._lock:
                if record["state"] == "cancelled":
                    return None
                record["state"] = "running"
                record["started_at"] = time.time()
            try:
                result = function(TaskContext(self, task_id))
            except Exception as exc:
                with self._lock:
                    self._fail_stage_locked(
                        record,
                        error_code=getattr(exc, "code", "TASK_FAILED"),
                        error_message=str(exc),
                    )
                    record["state"] = "failed"
                    record["error_code"] = getattr(exc, "code", "TASK_FAILED")
                    record["error_message"] = str(exc)
                    record["finished_at"] = time.time()
                    record["mutation_active"] = False
                self._prune()
                return None
            with self._lock:
                self._complete_stage_locked(record)
                record["state"] = "succeeded"
                record["result"] = result
                record["finished_at"] = time.time()
                record["mutation_active"] = False
            self._prune()
            return result

        future = self._executor.submit(run)
        with self._lock:
            record["future"] = future
        return task_id

    def _stage(
        self,
        task_id: str,
        stage_id: str,
        *,
        mutation: bool,
        idempotency_key: str | None = None,
        object_ref: str | None = None,
        expected: Any = None,
    ) -> None:
        with self._lock:
            record = self._tasks[task_id]
            self._complete_stage_locked(record)
            if (
                mutation
                and idempotency_key
                and idempotency_key in record["completed_mutation_keys"]
            ):
                raise MutationAlreadyCompleted(
                    f"mutation has already completed: {idempotency_key}"
                )
            record["current_stage"] = stage_id
            record["mutation_active"] = mutation
            record["stage_events"].append(
                {
                    "stage_id": stage_id,
                    "state": "running",
                    "mutation": mutation,
                    "idempotency_key": idempotency_key,
                    "object_ref": object_ref,
                    "expected": expected,
                    "actual": None,
                    "error_code": None,
                    "error_message": None,
                }
            )

    def _complete_stage(self, task_id: str, *, actual: Any = None) -> None:
        with self._lock:
            self._complete_stage_locked(self._tasks[task_id], actual=actual)

    def _complete_stage_locked(self, record: dict[str, Any], *, actual: Any = None) -> None:
        current = record["current_stage"]
        if current is None:
            return
        if current not in record["completed_stages"]:
            record["completed_stages"].append(current)
        event = record["stage_events"][-1]
        if event["state"] == "running":
            event["state"] = "completed"
            if actual is not None:
                event["actual"] = actual
            key = event["idempotency_key"]
            if event["mutation"] and key and key not in record["completed_mutation_keys"]:
                record["completed_mutation_keys"].append(key)
        record["current_stage"] = None
        record["mutation_active"] = False

    def _fail_stage(
        self,
        task_id: str,
        *,
        error_code: str,
        error_message: str,
        actual: Any = None,
    ) -> None:
        with self._lock:
            self._fail_stage_locked(
                self._tasks[task_id],
                error_code=error_code,
                error_message=error_message,
                actual=actual,
            )

    @staticmethod
    def _fail_stage_locked(
        record: dict[str, Any],
        *,
        error_code: str,
        error_message: str,
        actual: Any = None,
    ) -> None:
        if not record["current_stage"] or not record["stage_events"]:
            return
        event = record["stage_events"][-1]
        if event["state"] == "running":
            event["state"] = "failed"
            event["actual"] = actual
            event["error_code"] = error_code
            event["error_message"] = error_message
        record["mutation_active"] = False

    def status(self, task_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._tasks[task_id]
            completed = list(record["completed_stages"])
            if record["state"] == "succeeded" and record["current_stage"]:
                if record["current_stage"] not in completed:
                    completed.append(record["current_stage"])
            return {
                key: value
                for key, value in record.items()
                if key != "future"
            } | {"completed_stages": completed}

    def cancel(self, task_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._tasks[task_id]
            future: Future | None = record["future"]
            if record["state"] == "queued" and future is not None and future.cancel():
                record["state"] = "cancelled"
                record["finished_at"] = time.time()
                return self.status(task_id)
            return {
                **self.status(task_id),
                "error_code": "TASK_CANCEL_NOT_SAFE",
                "error_message": "Running Origin tasks cannot be cancelled safely",
            }

    def _prune(self) -> None:
        with self._lock:
            while len(self._tasks) > self.max_results:
                removable = next(
                    (
                        task_id
                        for task_id, record in self._tasks.items()
                        if record["state"] in {"succeeded", "failed", "cancelled"}
                    ),
                    None,
                )
                if removable is None:
                    break
                removed = self._tasks.pop(removable, None)
                if removed and removed.get("idempotency_key"):
                    self._idempotency.pop(removed["idempotency_key"], None)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=True)
