import time

import pytest

from origin_com_automation.com.errors import OriginTimeoutError
from origin_com_automation.com.worker import SerialComWorker


def test_worker_initializes_and_finalizes_one_sta_thread():
    events = []
    worker = SerialComWorker(
        initialize=lambda: events.append("init"),
        finalize=lambda: events.append("finalize"),
    )
    worker.start()

    assert worker.submit(lambda: 2 + 2) == 4

    worker.stop()

    assert events == ["init", "finalize"]


def test_worker_reports_timeout_but_keeps_queue_serialized():
    worker = SerialComWorker()
    worker.start()

    with pytest.raises(OriginTimeoutError):
        worker.submit(lambda: time.sleep(0.05), timeout=0.001)

    assert worker.submit(lambda: "after", timeout=1.0) == "after"
    worker.stop()
