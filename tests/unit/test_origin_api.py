import time
import sys
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from origin_com_automation.com.origin_api import OriginController, is_origin_process_name
from origin_com_automation.com.errors import OriginTimeoutError


class InlineWorker:
    def submit(self, fn, *, timeout=None):
        return fn()


class TimeoutAfterStartWorker:
    def __init__(self):
        self.calls = 0

    def submit(self, fn, *, timeout=None):
        self.calls += 1
        if self.calls == 2:
            raise OriginTimeoutError("timed out")
        return fn()


class RetryableComError(Exception):
    hresult = -2147418111  # RPC_E_CALL_REJECTED


class TransientWorker:
    def __init__(self):
        self.calls = 0

    def submit(self, fn, *, timeout=None):
        self.calls += 1
        if self.calls == 1:
            raise RetryableComError("Origin is busy")
        return fn()


class RpcDisconnectedError(Exception):
    hresult = -2147417848


class DisconnectAfterStartWorker:
    def __init__(self):
        self.calls = 0

    def submit(self, fn, *, timeout=None):
        self.calls += 1
        if self.calls == 2:
            raise RpcDisconnectedError("RPC disconnected")
        return fn()


def test_origin_process_name_accepts_windows_api_variants():
    assert is_origin_process_name("Origin64.exe")
    assert is_origin_process_name("Origin64")
    assert not is_origin_process_name("Origin64 Cleanup Watchdog")


def test_idempotent_com_call_retries_only_known_transient_hresult():
    worker = TransientWorker()
    controller = OriginController(worker=worker, sleep_fn=lambda _: None)

    result = controller._submit(lambda: {"read": True}, retryable=True)

    assert result.success is True
    assert worker.calls == 2
    assert result.warnings == ["Retried once after RPC_CALL_REJECTED"]


def test_non_idempotent_com_call_does_not_retry_transient_hresult():
    worker = TransientWorker()
    controller = OriginController(worker=worker, sleep_fn=lambda _: None)

    result = controller._submit(lambda: {"write": True})

    assert result.success is False
    assert result.error_code == "RPC_CALL_REJECTED"
    assert worker.calls == 1


def test_rpc_disconnect_reports_owned_origin_process_disappearance():
    app = FakeOriginApp()
    worker = DisconnectAfterStartWorker()
    snapshots = iter([set(), {101}, set()])
    controller = OriginController(
        worker=worker,
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success

    result = controller.read_worksheet("Book1")

    assert result.success is False
    assert result.error_code == "ORIGIN_PROCESS_TERMINATED"
    assert any("PID 101 disappeared" in warning for warning in result.warnings)


class FakeOriginApp:
    def __init__(self):
        self.Version = "10.1.0.178"
        self.Visible = None
        self.begin_session_calls = 0
        self.end_session_calls = 0
        self.exit_calls = 0
        self.loads = []
        self.puts = []
        self.sets = []
        self.finds = []
        self.sheet_data = ((1, 2), (3, 4))
        self.run_calls = 0
        self.new_project_result = True
        self.saves = []
        self.execute_result = True
        self.execute_scripts = []
        self.lt_strings = {}
        self.get_data_calls = []
        self.Name = "Sheet1"
        self.LongName = ""
        self.Rows = 2
        self._cols = 9
        self.Columns = FakeCollection([FakeWorksheetColumn(self, index) for index in range(9)])

    @property
    def Cols(self):
        return self._cols

    @Cols.setter
    def Cols(self, value):
        self._cols = int(value)

    def BeginSession(self):
        self.begin_session_calls += 1

    def EndSession(self):
        self.end_session_calls += 1

    def Exit(self):
        self.exit_calls += 1

    def Load(self, path, readonly):
        self.loads.append((path, readonly))
        return True

    def PutWorksheet(self, name, data, row, column):
        self.puts.append((name, data, row, column))
        return True

    def GetWorksheet(self, name, r1, c1, r2, c2, data_format):
        return self.sheet_data

    def FindWorksheet(self, name):
        self.finds.append(name)
        return self

    def CreatePage(self, page_type, name, template, option):
        return name

    def ClearData(self, *args):
        self.sheet_data = ()
        return True

    def SetData(self, data, row, column):
        self.sets.append((data, row, column))
        self.sheet_data = tuple(tuple(item for item in values) for values in data)
        return True

    def GetData(self, r1, c1, r2, c2, data_format):
        self.get_data_calls.append((r1, c1, r2, c2, data_format))
        rows = self.sheet_data[r1 : None if r2 == -1 else r2 + 1]
        return tuple(
            row[c1 : None if c2 == -1 else c2 + 1]
            for row in rows
        )

    def FindCol(self, name, start, case_sensitive):
        return FakeObject(Index={"A": 0, "B": 1}[name])

    def Execute(self, script):
        self.execute_scripts.append(script)
        return self.execute_result

    def LTStr(self, name):
        return self.lt_strings.get(name, "")

    def LTVar(self, name):
        return 42

    def Run(self):
        self.run_calls += 1
        return True

    def NewProject(self):
        return self.new_project_result

    def Save(self, path):
        self.saves.append(path)
        with open(path, "wb") as handle:
            handle.write(b"saved-project" + b"x" * 128)
        return True


class FakeCollection:
    def __init__(self, items):
        self._items = items
        self.Count = len(items)

    def Item(self, index):
        return self._items[index]


class FakeObject:
    def __init__(self, **values):
        for key, value in values.items():
            setattr(self, key, value)


class FakeWorksheetColumn:
    def __init__(self, parent, index):
        self.parent = parent
        self.Index = index
        self.Name = chr(ord("A") + index)
        self.LongName = ""
        self.Units = ""
        self.Comments = ""
        self.DataFormat = 0
        self.TextAndNumericSetAlwaysAsText = False

    def SetData(self, values, offset=0):
        rows = [list(row) for row in self.parent.sheet_data]
        required_rows = offset + len(values)
        while len(rows) < required_rows:
            rows.append([None] * self.parent.Cols)
        for row in rows:
            while len(row) < self.parent.Cols:
                row.append(None)
        for position, value in enumerate(values, start=offset):
            rows[position][self.Index] = value
        self.parent.sheet_data = tuple(tuple(row) for row in rows)
        self.parent.sets.append((list(values), offset, self.Index))
        return True

    def GetData(self, data_format, start, end, *optional):
        rows = self.parent.sheet_data[start : None if end == -1 else end + 1]
        return tuple(
            (row[self.Index] if self.Index < len(row) else None,)
            for row in rows
        )


def test_start_marks_new_process_as_owned_and_sets_visibility():
    app = FakeOriginApp()
    snapshots = iter([set(), {101}, set()])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )

    result = controller.start(progid="Origin.Application", visible=False, attach=False)

    assert result.success is True
    assert result.data["owned"] is True
    assert result.data["pid"] == 101
    assert result.origin_version == "10.1.0.178"
    assert app.Visible == 0
    assert app.begin_session_calls == 0


def test_start_waits_for_delayed_owned_process_visibility():
    app = FakeOriginApp()
    snapshots = iter([set(), set(), set(), {101}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
        sleep_fn=lambda _: None,
    )

    result = controller.start(progid="Origin.Application", visible=False, attach=False)

    assert result.success is True
    assert result.data["owned"] is True
    assert result.data["pid"] == 101


def test_start_refuses_unverified_implicit_attachment_without_exiting_user_app():
    app = FakeOriginApp()
    snapshots = iter([{55}, {55}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )

    result = controller.start(progid="Origin.Application", attach=False)

    assert result.success is False
    assert result.error_code == "OWNERSHIP_UNVERIFIED"
    assert app.exit_calls == 0


def test_open_project_without_session_does_not_create_working_copy(tmp_path):
    source = tmp_path / "source.opju"
    source.write_bytes(b"project")
    working = tmp_path / "working.opju"
    controller = OriginController(worker=InlineWorker())

    result = controller.open_project(
        source_path=str(source),
        working_copy_path=str(working),
    )

    assert result.error_code == "NO_ACTIVE_SESSION"
    assert not working.exists()


def test_project_copy_and_worksheet_io_use_the_owned_app(tmp_path):
    app = FakeOriginApp()
    snapshots = iter([set(), {101}, {101}, set()])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success
    source = tmp_path / "source.opju"
    source.write_bytes(b"project")
    working = tmp_path / "working.opju"

    opened = controller.open_project(source_path=str(source), working_copy_path=str(working))
    written = controller.write_worksheet("Book1", [[1, 2], [3, 4]])
    read = controller.read_worksheet("Book1", r1=0, c1=0, r2=1, c2=1)
    saved_path = tmp_path / "result.opju"
    saved = controller.save_project_copy(target_path=str(saved_path))
    blocked_source_save = controller.save_project_copy(
        target_path=str(source),
        overwrite=True,
    )

    assert opened.success is True
    assert opened.data["completed_stages"] == ["copy", "load", "activate", "validate"]
    assert app.loads == [(str(working.resolve()), False)]
    assert written.success is True
    assert app.finds[0] == "Book1"
    assert app.sets[0][0] == [[1, 2], [3, 4]]
    assert read.data["values"] == [[1, 2], [3, 4]]
    assert saved.success is True
    assert app.run_calls == 1
    assert app.saves == [str(saved_path.resolve())]
    assert blocked_source_save.error_code == "SOURCE_OVERWRITE_BLOCKED"
    assert source.read_bytes() == b"project"

    stopped = controller.shutdown()
    assert stopped.success is True
    assert app.end_session_calls == 0
    assert app.exit_calls == 0
    assert app.execute_scripts[-2:] == [
        "doc -s;",
        "def timerproc { exit; } timer 1;",
    ]


def test_overwrite_save_never_accepts_an_unchanged_stale_target(tmp_path):
    class NoOpSaveApp(FakeOriginApp):
        IsModified = True

        def Save(self, path):
            self.saves.append(path)
            return None

    app = NoOpSaveApp()
    snapshots = iter([set(), {101}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success
    target = tmp_path / "existing.opju"
    target.write_bytes(b"STALE-OLD-FILE")

    result = controller.save_project_copy(target_path=str(target), overwrite=True)

    assert result.success is False
    assert result.error_code == "PROJECT_SAVE_UNCONFIRMED"
    assert target.read_bytes() == b"STALE-OLD-FILE"


def test_failed_project_close_keeps_source_overwrite_protection(tmp_path):
    app = FakeOriginApp()
    snapshots = iter([set(), {101}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success
    source = tmp_path / "source.opju"
    source.write_bytes(b"ORIGINAL")
    assert controller.open_project(source_path=str(source)).success
    app.new_project_result = False

    closed = controller.close_project(discard_changes=True)
    overwrite = controller.save_project_copy(target_path=str(source), overwrite=True)

    assert closed.success is False
    assert closed.error_code == "PROJECT_CLOSE_UNCONFIRMED"
    assert overwrite.error_code == "SOURCE_OVERWRITE_BLOCKED"
    assert source.read_bytes() == b"ORIGINAL"


def test_all_source_projects_remain_protected_for_the_session(tmp_path):
    app = FakeOriginApp()
    snapshots = iter([set(), {101}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success
    source_a = tmp_path / "a.opju"
    source_b = tmp_path / "b.opju"
    source_a.write_bytes(b"SOURCE-A")
    source_b.write_bytes(b"SOURCE-B")
    assert controller.open_project(source_path=str(source_a)).success
    assert controller.open_project(source_path=str(source_b)).success

    overwrite = controller.save_project_copy(target_path=str(source_a), overwrite=True)

    assert overwrite.error_code == "SOURCE_OVERWRITE_BLOCKED"
    assert source_a.read_bytes() == b"SOURCE-A"


def test_source_is_protected_even_when_project_load_raises(tmp_path):
    class PartialLoadApp(FakeOriginApp):
        def Load(self, path, readonly):
            self.loads.append((path, readonly))
            raise RuntimeError("RPC disconnected after load")

    app = PartialLoadApp()
    snapshots = iter([set(), {101}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success
    source = tmp_path / "source.opju"
    source.write_bytes(b"SOURCE")

    opened = controller.open_project(source_path=str(source))
    overwrite = controller.save_project_copy(target_path=str(source), overwrite=True)

    assert opened.success is False
    assert overwrite.error_code == "SOURCE_OVERWRITE_BLOCKED"
    assert source.read_bytes() == b"SOURCE"


def test_moved_source_file_remains_protected_by_file_identity(tmp_path):
    app = FakeOriginApp()
    snapshots = iter([set(), {101}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success
    source = tmp_path / "source.opju"
    moved = tmp_path / "renamed-source.opju"
    source.write_bytes(b"SOURCE")
    assert controller.open_project(source_path=str(source)).success
    source.rename(moved)

    overwrite = controller.save_project_copy(target_path=str(moved), overwrite=True)

    assert overwrite.error_code == "SOURCE_OVERWRITE_BLOCKED"
    assert moved.read_bytes() == b"SOURCE"


def test_attached_exclusive_session_ends_lock_and_blocks_mutation():
    app = FakeOriginApp()
    snapshots = iter([{55}, {55}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )

    started = controller.start(
        progid="Origin.ApplicationSI",
        attach=True,
        exclusive=True,
    )
    blocked = controller.write_worksheet("Book1", [[1]])
    stopped = controller.shutdown()

    assert started.success is True
    assert started.data["owned"] is False
    assert app.Visible is None
    assert app.begin_session_calls == 1
    assert blocked.error_code == "ATTACHED_SESSION_PROTECTED"
    assert app.puts == []
    assert stopped.success is True
    assert app.end_session_calls == 1
    assert app.exit_calls == 0


def test_attach_without_existing_instance_is_rejected_before_dispatch():
    app = FakeOriginApp()
    snapshots = iter([set()])
    calls = []
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: calls.append((progid, attach)) or app,
        process_snapshot=lambda: next(snapshots),
    )

    started = controller.start(attach=True, visible=False)
    stopped = controller.shutdown()

    assert started.success is False
    assert started.error_code == "NO_EXISTING_ORIGIN"
    assert calls == []
    assert stopped.success is True
    assert app.exit_calls == 0


def test_attach_never_claims_new_pid_or_exits_ambiguous_proxy():
    app = FakeOriginApp()
    snapshots = iter([{55}, {55, 77}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )

    started = controller.start(attach=True)
    stopped = controller.shutdown()

    assert started.success is False
    assert started.error_code == "OWNERSHIP_UNVERIFIED"
    assert stopped.success is True
    assert app.exit_calls == 0


def test_attach_defaults_to_single_instance_progid():
    app = FakeOriginApp()
    snapshots = iter([{55}, {55}])
    calls = []
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: calls.append((progid, attach)) or app,
        process_snapshot=lambda: next(snapshots),
    )

    result = controller.start(attach=True)

    assert result.success is True
    assert calls == [("Origin.ApplicationSI", True)]


def test_list_objects_returns_typed_pages_layers_and_data_sources():
    worksheet = FakeObject(
        Name="Sheet1",
        LongName="Transfer Data",
        Index=0,
        Rows=3,
        Cols=2,
        DataObjectBases=FakeCollection([]),
    )
    workbook = FakeObject(
        Name="Book1",
        LongName="IVG",
        TypeName="Worksheet",
        PEPath="/Book1",
        Layers=FakeCollection([worksheet]),
    )
    graph_layer = FakeObject(
        Name="Layer1",
        LongName="",
        Index=0,
        DataPlots=FakeCollection([FakeObject(Name="Plot1", TypeName="DataPlot")]),
        DataObjectBases=FakeCollection([]),
    )
    graph_page = FakeObject(
        Name="Graph1",
        LongName="Transfer",
        TypeName="Graph",
        PEPath="/Graph1",
        Layers=FakeCollection([graph_layer]),
    )
    app = FakeOriginApp()
    app.PageBases = FakeCollection([])
    app.WorksheetPages = FakeCollection([workbook])
    app.GraphPages = FakeCollection([graph_page])
    app.MatrixPages = FakeCollection([])
    snapshots = iter([set(), {101}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success

    result = controller.list_objects()

    assert result.success is True
    assert result.data["workbooks"][0]["name"] == "Book1"
    assert result.data["worksheets"][0]["name"] == "Sheet1"
    assert result.data["worksheets"][0]["id"] == "[Book1]Sheet1"
    assert result.data["graphs"][0]["name"] == "Graph1"
    assert result.data["graph_layers"][0]["id"] == "[Graph1]1"
    assert any(item["name"] == "Plot1" for item in result.data["data_sources"])


def test_named_columns_accept_origin_data_object_indices():
    app = FakeOriginApp()
    snapshots = iter([set(), {101}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success

    result = controller.run_analysis(
        worksheet_name="[Book1]Sheet1",
        method="linear_fit",
        x_column="A",
        y_column="B",
    )

    assert result.success is True
    assert result.data["result"]["slope"] == pytest.approx(1.0)


def test_analysis_applies_explicit_row_range_filters_and_order():
    app = FakeOriginApp()
    app.sheet_data = ((0, 0), (1, 1), (2, 4), (3, 9))
    snapshots = iter([set(), {101}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success

    result = controller.run_analysis(
        worksheet_name="Book1",
        method="derivative",
        x_column=0,
        y_column=1,
        options={"derivative_method": "forward"},
        row_start=1,
        row_end=3,
        filters=[{"column": "y", "operator": "le", "value": 4}],
        row_order="reverse",
    )

    assert result.success is True
    assert app.get_data_calls[-1] == (1, 0, 3, -1, 2)
    assert result.data["selection"]["rows_after_filter"] == 2
    assert result.data["selection"]["row_order"] == "reverse"
    assert result.data["result"]["x"] == [2.0]
    assert result.data["result"]["derivative"] == pytest.approx([3.0])


def test_labtalk_falls_back_to_numeric_variable_and_rejects_false_execute():
    app = FakeOriginApp()
    snapshots = iter([set(), {101}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success

    numeric = controller.execute_labtalk(script="x=42;", result_variable="x")
    app.execute_result = False
    failed = controller.execute_labtalk(script="this is invalid;")

    assert numeric.success is True
    assert numeric.data["result"] == 42
    assert failed.success is False
    assert failed.error_code == "LABTALK_EXECUTION_FAILED"


def test_labtalk_returns_named_outputs_and_explicit_warning_variable():
    app = FakeOriginApp()
    app.lt_strings = {"message": "done", "warnings": "first warning\nsecond warning"}
    snapshots = iter([set(), {101}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success

    result = controller.execute_labtalk(
        script="message$=done;",
        result_string_variables=["message"],
        warning_variable="warnings",
    )

    assert result.success is True
    assert result.data["output"] == {"message": "done"}
    assert result.warnings == ["first warning", "second warning"]


def test_concurrent_starts_create_only_one_origin_instance():
    app = FakeOriginApp()
    calls = []
    snapshots = iter([set(), {101}])

    def dispatch(progid, attach):
        calls.append((progid, attach))
        time.sleep(0.05)
        return app

    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=dispatch,
        process_snapshot=lambda: next(snapshots),
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: controller.start(), range(2)))

    assert all(result.success for result in results)
    assert len(calls) == 1
    assert sum(bool(result.data.get("already_active")) for result in results) == 1


def test_import_legacy_xls_uses_xlrd(monkeypatch, tmp_path):
    app = FakeOriginApp()
    snapshots = iter([set(), {101}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success
    source = tmp_path / "legacy.xls"
    source.write_bytes(b"xls")
    fake_sheet = SimpleNamespace(nrows=2, row_values=lambda index: [["x", "y"], [1, 2]][index])
    fake_book = SimpleNamespace(
        sheet_names=lambda: ["Data"],
        sheet_by_name=lambda name: fake_sheet,
    )
    monkeypatch.setitem(
        sys.modules,
        "xlrd",
        SimpleNamespace(open_workbook=lambda path, on_demand: fake_book),
    )

    result = controller.import_data(file_path=str(source), worksheet_name="Legacy")

    assert result.success is True
    assert [app.Columns.Item(index).GetData(0, 0, 0)[0][0] for index in range(2)] == [1, 2]
    assert result.data["column_labels"] == ["x", "y"]
    assert result.data["rows"] == 1


def test_timeout_poisons_session_and_blocks_follow_up_calls():
    app = FakeOriginApp()
    snapshots = iter([set(), {101}])
    worker = TimeoutAfterStartWorker()
    controller = OriginController(
        worker=worker,
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success

    timed_out = controller.write_worksheet("Book1", [[1]])
    blocked = controller.read_worksheet("Book1")

    assert timed_out.error_code == "COM_TIMEOUT"
    assert blocked.error_code == "SESSION_POISONED"
    assert worker.calls == 2


def test_open_project_timeout_reports_the_load_stage(tmp_path):
    app = FakeOriginApp()
    worker = TimeoutAfterStartWorker()
    snapshots = iter([set(), {101}])
    controller = OriginController(
        worker=worker,
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success
    source = tmp_path / "source.opju"
    source.write_bytes(b"project")

    result = controller.open_project(source_path=str(source))

    assert result.error_code == "COM_TIMEOUT"
    assert result.data["stage"] == "load"
    assert any(tmp_path.glob("source.codex-working-*.opju"))


def test_shutdown_exit_schedule_failure_discards_proxy_before_next_start():
    class ExitScheduleFailApp(FakeOriginApp):
        def Execute(self, script):
            super().Execute(script)
            if script == "def timerproc { exit; } timer 1;":
                raise RuntimeError("Exit scheduling failed")
            return True

    first = ExitScheduleFailApp()
    second = FakeOriginApp()
    apps = iter([first, second])
    snapshots = iter([set(), {101}, {101}, {101}, {101, 102}])
    calls = []
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: calls.append((progid, attach)) or next(apps),
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success

    failed_shutdown = controller.shutdown()
    restarted = controller.start(progid="Origin.Application")

    assert failed_shutdown.success is False
    assert restarted.success is True
    assert restarted.data.get("already_active") is not True
    assert len(calls) == 2
