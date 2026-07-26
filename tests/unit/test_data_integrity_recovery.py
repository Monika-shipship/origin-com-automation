from __future__ import annotations

import csv
from hashlib import sha256
import time
from types import SimpleNamespace

from openpyxl import Workbook

from origin_com_automation.com.errors import OriginTimeoutError
from origin_com_automation.com.origin_api import OriginController, _system_worksheet_template


class InlineWorker:
    def submit(self, fn, *, timeout=None):
        return fn()


class PoisonAfterStartWorker:
    def __init__(self):
        self.calls = 0

    def submit(self, fn, *, timeout=None):
        self.calls += 1
        if self.calls == 2:
            raise OriginTimeoutError("blocked COM call")
        return fn()


class Column:
    def __init__(self, index: int, *, accept_write: bool = True, persist_write: bool = True):
        self.Index = index
        self.Name = chr(ord("A") + index)
        self.LongName = f"template-{self.Name}"
        self.Units = "template-unit"
        self.Comments = "template-comment"
        self.Type = 3 if index == 0 else 0
        self.DataFormat = 9
        self.TextAndNumericSetAlwaysAsText = True
        self.values = [999.0] * 162
        self.accept_write = accept_write
        self.persist_write = persist_write

    def SetData(self, values, offset=0):
        if not self.accept_write:
            return False
        if self.persist_write:
            required = offset + len(values)
            if len(self.values) < required:
                self.values.extend([None] * (required - len(self.values)))
            self.values[offset:required] = list(values)
        return True

    def GetData(self, data_format, start, end, *optional):
        values = self.values[start : None if end == -1 else end + 1]
        return tuple((value,) for value in values)


class Columns:
    def __init__(self, items):
        self.items = list(items)

    @property
    def Count(self):
        return len(self.items)

    def Item(self, index):
        return self.items[index]


class Worksheet:
    def __init__(self, *, accept_write: bool = True, persist_write: bool = True):
        self.Name = "Sheet1"
        self.LongName = "IVG-12.csv"
        self.Rows = 162
        self._cols = 9
        self.Columns = Columns(
            [
                Column(i, accept_write=accept_write, persist_write=persist_write)
                for i in range(self._cols)
            ]
        )

    @property
    def Cols(self):
        return self._cols

    @Cols.setter
    def Cols(self, value):
        value = int(value)
        while len(self.Columns.items) < value:
            self.Columns.items.append(Column(len(self.Columns.items)))
        self.Columns.items = self.Columns.items[:value]
        self._cols = value

    def ClearData(self, *args):
        for column in self.Columns.items:
            column.values = []
        return True

    def SetData(self, rows, row, column):
        accepted = True
        width = max((len(item) for item in rows), default=0)
        for offset in range(width):
            accepted = self.Columns.Item(column + offset).SetData(
                [item[offset] if offset < len(item) else None for item in rows],
                row,
            ) and accepted
        return accepted

    def GetData(self, r1, c1, r2, c2, data_format):
        end_row = self.Rows - 1 if r2 == -1 else r2
        end_col = self.Cols - 1 if c2 == -1 else c2
        return tuple(
            tuple(
                self.Columns.Item(col).values[row]
                if row < len(self.Columns.Item(col).values)
                else None
                for col in range(c1, end_col + 1)
            )
            for row in range(r1, end_row + 1)
        )


class DataApp:
    Version = "10.1.0.178"

    def __init__(self, *, accept_write: bool = True, persist_write: bool = True):
        self.Visible = None
        self.sheet = Worksheet(accept_write=accept_write, persist_write=persist_write)
        self.page = SimpleNamespace(Name="Benchmark", LongName="IVG-12.csv")
        self.WorksheetPages = SimpleNamespace(Item=lambda name: self.page)

    def CreatePage(self, page_type, name, template, option):
        self.page.Name = name
        return name

    def FindWorksheet(self, name):
        return self.sheet


class SegmentedLabTalkApp(DataApp):
    def __init__(self):
        super().__init__()
        self.scripts = []

    def Execute(self, script):
        self.scripts.append(script)
        return script != "bad;"

    def LTVar(self, name):
        return 7

    def LTStr(self, name):
        return ""


def started_controller(app, *, worker=None, snapshots=None):
    if snapshots is None:
        snapshots = iter([set(), {41001}])
    controller = OriginController(
        worker=worker or InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success
    return controller


def make_mixed_xlsx(path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "p-WSe2-only"
    sheet.append(["Lch", "Rc", "Ion", "on/off ratio", "Units"])
    rows = [
        [20, 0.041, 2260, "≈1", "μA/μm"],
        [40, "NA", 1700, 1.0e6, "μA/μm"],
        [80, 0.12, 950, None, "μA/μm"],
    ]
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def test_xlsx_import_profiles_every_column_and_preserves_ion_values(tmp_path):
    source = tmp_path / "mixed-benchmark.xlsx"
    make_mixed_xlsx(source)
    app = DataApp()
    controller = started_controller(app)

    result = controller.import_data(
        file_path=str(source),
        worksheet_name="WSe2Benchmark",
        sheet_name="p-WSe2-only",
        has_header=True,
        source_mode="snapshot",
    )

    assert result.success is True
    assert result.data["worksheet_ref"] == "[WSe2Benchmark]Sheet1"
    profiles = {item["label"]: item for item in result.data["column_profiles"]}
    assert profiles["Ion"]["source"] == {
        "non_empty_count": 3,
        "numeric_count": 3,
        "text_count": 0,
        "missing_count": 0,
    }
    assert profiles["Ion"]["destination"] == profiles["Ion"]["source"]
    assert profiles["Ion"]["first_value"] == 2260
    assert profiles["Ion"]["last_value"] == 950
    assert app.sheet.Columns.Item(1).DataFormat == 9
    assert app.sheet.Columns.Item(2).DataFormat == 0
    assert app.sheet.Rows == 3
    assert app.sheet.Cols == 5
    assert app.sheet.LongName == ""
    assert app.page.LongName == "WSe2Benchmark"
    assert result.data["template_reset"]["initial_rows"] == 162
    assert result.data["template_reset"]["initial_columns"] == 9


def test_default_import_uses_data_connector_without_static_block_write(tmp_path):
    source = tmp_path / "linked.csv"
    source.write_text("x,y\n1,2\n3,4\n", encoding="utf-8")

    class LinkedWorksheet(Worksheet):
        def __init__(self):
            super().__init__()
            self.connected = False
            self.source = ""
            self.options = (
                '<OriginStorage><CSV/><Settings><heading>0</heading>'
                '</Settings></OriginStorage>'
            )
            self.static_set_calls = 0
            self.refreshes = 0

        def SetData(self, rows, row, column):
            self.static_set_calls += 1
            return super().SetData(rows, row, column)

        def Execute(self, script):
            if "wbook.dc.add" in script:
                self.connected = True
            elif "wbook.dc.remove" in script:
                self.connected = False
            return 1

        def DoMethod(self, name, argument):
            if name == "DC.Import":
                self.refreshes += 1
                with open(self.source, encoding="utf-8", newline="") as handle:
                    rows = list(csv.reader(handle))
                labels, values = rows[0], rows[1:]
                self.Cols = len(labels)
                self.Rows = len(values)
                for index, label in enumerate(labels):
                    column = self.Columns.Item(index)
                    column.LongName = label
                    column.values = [float(row[index]) for row in values]
            return 1

        def GetNumProp(self, name):
            return int(name == "HasDC" and self.connected)

        def GetStrProp(self, name):
            return {
                "DC.Source": self.source,
                "DC.Optn": self.options,
            }.get(name, "")

        def SetStrProp(self, name, value):
            if name == "DC.Source":
                self.source = value
            elif name == "DC.Optn":
                self.options = value
            return 1

    class LinkedApp(DataApp):
        def __init__(self):
            super().__init__()
            self.sheet = LinkedWorksheet()
            self.sheet.Parent = self.page

        def LTVar(self, name):
            return 1

        def Execute(self, script):
            return 1

    app = LinkedApp()
    controller = started_controller(app)

    result = controller.import_data(
        file_path=str(source),
        worksheet_name="LinkedData",
        has_header=True,
        source_mode="linked",
    )

    assert result.success is True
    assert result.data["source_mode"] == "linked"
    assert result.data["worksheet_ref"] == "[LinkedData]Sheet1"
    assert result.data["connector"]["connected"] is True
    assert result.data["connector"]["source"] == str(source.resolve())
    assert result.data["connector"]["selection"] is None
    assert result.data["connector"]["has_header"] is True
    assert "<heading>1</heading>" in app.sheet.options
    assert result.data["source_sha256"] == sha256(source.read_bytes()).hexdigest()
    assert result.data["rows"] == 2
    assert result.data["columns"] == 2
    assert result.data["column_profiles"][1]["first_value"] == 2.0
    assert result.data["column_profiles"][1]["last_value"] == 4.0
    assert app.sheet.static_set_calls == 0
    assert app.sheet.refreshes == 1


def test_system_origin_template_takes_precedence_over_user_template(tmp_path):
    program = tmp_path / "Origin2024"
    template = program / "Localization" / "E" / "ORIGIN.otwu"
    template.parent.mkdir(parents=True)
    template.write_bytes(b"system-template")
    app = SimpleNamespace(Path=lambda path_type: str(program))

    selected, is_system = _system_worksheet_template(app)

    assert selected == str(template.resolve())
    assert is_system is True


def test_write_fails_when_setdata_explicitly_rejects_the_values():
    app = DataApp(accept_write=False)
    controller = started_controller(app)

    result = controller.write_worksheet("[Benchmark]Sheet1", [[2260]], row=0, column=2)

    assert result.success is False
    assert result.error_code == "WORKSHEET_WRITE_REJECTED"


def test_write_fails_when_readback_does_not_match():
    app = DataApp(persist_write=False)
    controller = started_controller(app)

    result = controller.write_worksheet("[Benchmark]Sheet1", [[2260]], row=0, column=2)

    assert result.success is False
    assert result.error_code == "WORKSHEET_WRITE_UNCONFIRMED"
    assert result.data["stage"] == "verify"


def test_poisoned_shutdown_returns_immediately_without_reusing_blocked_worker():
    app = DataApp()
    worker = PoisonAfterStartWorker()
    snapshots = iter([set(), {41001}, {41001}])
    controller = started_controller(app, worker=worker, snapshots=snapshots)
    assert controller.write_worksheet("[Benchmark]Sheet1", [[1]]).error_code == "COM_TIMEOUT"

    started = time.perf_counter()
    result = controller.shutdown()

    assert time.perf_counter() - started < 0.1
    assert result.success is False
    assert result.error_code == "SESSION_POISONED"
    assert result.data["recovery_tool"] == "origin_recover_session"
    assert worker.calls == 2


def test_abandon_poisoned_session_never_terminates_an_unproven_pid():
    app = DataApp()
    worker = PoisonAfterStartWorker()
    terminated = []
    snapshots = iter([set(), {41001}, {41001}])
    controller = OriginController(
        worker=worker,
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
        process_terminator=terminated.append,
    )
    assert controller.start(progid="Origin.Application").success
    assert controller.write_worksheet("[Benchmark]Sheet1", [[1]]).error_code == "COM_TIMEOUT"

    result = controller.abandon_poisoned_session()

    assert result.success is True
    assert result.data["previous_session_id"]
    assert result.data["owned_pid"] == 41001
    assert result.data["worker_abandoned"] is True
    assert result.data["process_cleanup_attempted"] is False
    assert result.data["process_cleanup_confirmed"] is False
    assert terminated == []


def test_segmented_labtalk_reports_the_exact_failed_segment():
    app = SegmentedLabTalkApp()
    controller = started_controller(app)

    result = controller.execute_labtalk(
        script="",
        segments=["x=1;", "bad;", "y=2;"],
    )

    assert result.success is False
    assert result.error_code == "LABTALK_EXECUTION_FAILED"
    assert result.data["stage"] == "execute_segment"
    assert result.data["failed_segment"] == 2
    assert result.data["failed_statement"] == "bad;"
    assert result.data["completed_segments"] == 1
    assert app.scripts == ["x=1;", "bad;"]
