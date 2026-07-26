"""A serialized STA worker for all Origin COM calls."""

from __future__ import annotations

import queue
import threading
from concurrent.futures import Future, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from typing import Any, Callable

from .errors import OriginAutomationError, OriginTimeoutError, WorkerNotRunningError


def _default_initialize() -> None:
    try:
        import pythoncom

        pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
    except ImportError:
        # Unit tests and non-Windows development can inject a fake initializer.
        return


def _default_finalize() -> None:
    try:
        import pythoncom

        pythoncom.CoUninitialize()
    except Exception:
        return


@dataclass
class _Job:
    fn: Callable[[], Any]
    future: Future


class SerialComWorker:
    """Run COM work in one dedicated, serialized apartment thread."""

    def __init__(
        self,
        *,
        initialize: Callable[[], None] = _default_initialize,
        finalize: Callable[[], None] = _default_finalize,
    ) -> None:
        self._initialize = initialize
        self._finalize = finalize
        self._jobs: queue.Queue[_Job | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._start_error: BaseException | None = None
        self._stop_lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            return
        self._ready.clear()
        self._start_error = None
        self._thread = threading.Thread(
            target=self._run,
            name="origin-com-sta",
            daemon=True,
        )
        self._thread.start()
        self._ready.wait(timeout=5.0)
        if self._start_error is not None:
            error = self._start_error
            self._thread = None
            raise OriginAutomationError(f"COM worker initialization failed: {error}") from error

    def submit(self, fn: Callable[[], Any], *, timeout: float | None = None) -> Any:
        if not self.is_running:
            raise WorkerNotRunningError("COM worker is not running")
        future: Future = Future()
        self._jobs.put(_Job(fn=fn, future=future))
        try:
            return future.result(timeout=timeout)
        except FutureTimeoutError as exc:
            raise OriginTimeoutError("Origin COM operation exceeded its timeout") from exc

    def stop(self, *, join_timeout: float = 5.0) -> None:
        with self._stop_lock:
            thread = self._thread
            if thread is None:
                return
            self._jobs.put(None)
            thread.join(timeout=join_timeout)
            if thread.is_alive():
                raise OriginAutomationError("COM worker did not stop before the shutdown timeout")
            self._thread = None

    def _run(self) -> None:
        try:
            self._initialize()
        except BaseException as exc:  # preserve the original startup failure for the caller
            self._start_error = exc
            self._ready.set()
            return
        self._ready.set()
        try:
            while True:
                job = self._jobs.get()
                if job is None:
                    return
                try:
                    if not job.future.set_running_or_notify_cancel():
                        continue
                    job.future.set_result(job.fn())
                except BaseException as exc:
                    job.future.set_exception(exc)
        finally:
            self._finalize()
