import pytest

from origin_com_automation.com.origin_api import OriginController
from origin_com_automation.native.common import NativeValidationError
from origin_com_automation.native.formulas import (
    build_column_formula_plan,
    execute_column_formula_plan,
)


class InlineWorker:
    def submit(self, fn, *, timeout=None):
        return fn()


class FormulaColumn:
    def __init__(self, parent, index, name):
        self.parent = parent
        self.Index = index
        self.Name = name
        self.LongName = name
        self.formula = ""
        self.script = ""
        self.formula_range = ""
        self.recalculate_mode = 0

    def GetStrProp(self, name):
        return {
            "Formula": self.formula,
            "Script": self.script,
            "FormulaRange": self.formula_range,
        }.get(name, "")

    def GetNumProp(self, name):
        return self.recalculate_mode if name == "SVRM" else -1.23456789e-300

    def GetData(self, data_format, start, end, *optional):
        stop = len(self.parent.data) if end == -1 else end + 1
        return tuple((row[self.Index],) for row in self.parent.data[start:stop])


class FormulaColumns:
    def __init__(self, parent):
        self.items = [
            FormulaColumn(parent, 0, "A"),
            FormulaColumn(parent, 1, "B"),
            FormulaColumn(parent, 2, "C"),
        ]
        self.Count = len(self.items)

    def Item(self, index):
        return self.items[index]


class FormulaSheet:
    def __init__(self):
        self.data = [[1.0, 10.0, None], [2.0, 20.0, None], [3.0, 30.0, None]]
        self.Rows = len(self.data)
        self.Cols = 3
        self.Columns = FormulaColumns(self)

    def FindCol(self, name, start, case_sensitive):
        for column in self.Columns.items:
            if name in {column.Name, column.LongName}:
                return column
        return None


class FormulaApp:
    Version = "10.1.0.178"

    def __init__(self):
        self.sheet = FormulaSheet()
        self.scripts = []

    def FindWorksheet(self, ref):
        return self.sheet if ref == "[Book1]Data" else None

    def Execute(self, script):
        self.scripts.append(script)
        column = self.sheet.Columns.Item(2)
        column.formula = "col(A)*col(B)"
        column.script = "double scale=1;"
        column.formula_range = "[1:3]"
        column.recalculate_mode = 1
        for row in self.sheet.data:
            row[2] = row[0] * row[1]
        return True


class TransformColumns:
    def __init__(self, parent):
        self.parent = parent
        self.items = [FormulaColumn(parent, 0, "A"), FormulaColumn(parent, 1, "B")]

    @property
    def Count(self):
        return len(self.items)

    def Item(self, index):
        return self.items[index]

    def append_to(self, count):
        while len(self.items) < count:
            index = len(self.items)
            for row in self.parent.data:
                row.append(None)
            self.items.append(FormulaColumn(self.parent, index, chr(ord("A") + index)))


class TransformSheet:
    def __init__(self):
        self.data = [[1.0, 10.0], [2.0, 20.0], [3.0, 30.0]]
        self.Rows = len(self.data)
        self._cols = 2
        self.Columns = TransformColumns(self)
        self.set_data_calls = []

    @property
    def Cols(self):
        return self._cols

    @Cols.setter
    def Cols(self, value):
        self._cols = int(value)
        if hasattr(self, "Columns"):
            self.Columns.append_to(self._cols)

    def FindCol(self, name, start, case_sensitive):
        for column in self.Columns.items:
            if name in {column.Name, column.LongName}:
                return column
        return None

    def SetData(self, values, row, column):
        self.set_data_calls.append((values, row, column))
        return True


class TransformApp:
    Version = "10.1.0.178"

    def __init__(self):
        self.sheet = TransformSheet()
        self.scripts = []

    def FindWorksheet(self, ref):
        return self.sheet if ref == "[Book1]Data" else None

    def Execute(self, script):
        self.scripts.append(script)
        target = self.sheet.Columns.Item(2)
        target.formula = "col(A)*col(B)"
        target.script = ""
        target.formula_range = ""
        target.recalculate_mode = 1
        for row in self.sheet.data:
            row[2] = row[0] * row[1]
        return True


def owned_controller(app):
    controller = OriginController(worker=InlineWorker())
    controller._app = app
    record = controller.sessions.register(
        progid="Origin.Application", pid=123, owned=True, visible=False
    )
    controller._session_id = record.session_id
    controller._origin_version = app.Version
    return controller


def test_formula_plan_preserves_formula_script_range_and_recalculation_mode():
    plan = build_column_formula_plan(
        worksheet_ref="[Book1]Data",
        column="C",
        formula="col(A)*col(B)",
        before_script="double scale=1;",
        row_start=0,
        row_end=2,
        recalculate_mode="auto",
    )

    assert plan.worksheet_ref == "[Book1]Data"
    assert plan.column_index == 2
    assert plan.target_range == "[Book1]Data!C[1:3]"
    assert plan.formula == "col(A)*col(B)"
    assert plan.before_script == "double scale=1;"
    assert plan.expected_formula_range == "[1:3]"
    assert plan.command == (
        'csetvalue col:=[Book1]Data!C[1:3] formula:="col(A)*col(B)" '
        'script:="double scale=1;" recalculate:=1;'
    )


def test_formula_plan_escapes_labtalk_string_delimiters_without_changing_metadata():
    plan = build_column_formula_plan(
        worksheet_ref="[Book1]Data",
        column=2,
        formula='col(A)+"literal"',
        before_script='string note$="quoted"; path$="C:\\data";',
    )

    assert plan.formula == 'col(A)+"literal"'
    assert plan.before_script == 'string note$="quoted"; path$="C:\\data";'
    assert 'formula:="col(A)+\\"literal\\""' in plan.command
    assert 'note$=\\"quoted\\"' in plan.command
    assert 'C:\\\\data' in plan.command


def test_formula_plan_quotes_a_worksheet_long_name_for_labtalk_ranges():
    plan = build_column_formula_plan(
        worksheet_ref="[Book1]native-defaults",
        column="C",
        formula="col(A)*col(B)",
    )

    assert plan.worksheet_ref == "[Book1]native-defaults"
    assert plan.target_range == '[Book1]"native-defaults"!C'
    assert 'col:=[Book1]"native-defaults"!C' in plan.command


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"formula": "   "}, "formula must not be empty"),
        ({"worksheet_ref": '[Book1]Data; del -all'}, "worksheet ref"),
        ({"column": "C;"}, "column"),
        ({"row_start": 3, "row_end": 2}, "row_end"),
        ({"recalculate_mode": "sometimes"}, "recalculation mode"),
    ],
)
def test_formula_plan_rejects_invalid_or_unsafe_inputs(kwargs, message):
    request = {
        "worksheet_ref": "[Book1]Data",
        "column": "C",
        "formula": "col(A)*col(B)",
    }
    request.update(kwargs)
    with pytest.raises(NativeValidationError, match=message):
        build_column_formula_plan(**request)


def test_formula_execution_requires_exact_metadata_readback():
    app = FormulaApp()
    column = app.sheet.Columns.Item(2)
    plan = build_column_formula_plan(
        worksheet_ref="[Book1]Data",
        column="C",
        formula="col(A)*col(B)",
        before_script="double scale=1;",
        row_start=0,
        row_end=2,
        recalculate_mode="auto",
    )

    result = execute_column_formula_plan(app, column, plan)

    assert result["metadata_verified"] is True
    assert result["formula"] == "col(A)*col(B)"
    assert result["before_script"] == "double scale=1;"
    assert result["formula_range"] == "[1:3]"
    assert result["recalculate_mode"] == "auto"


def test_formula_execution_rejects_mismatched_recalculation_readback():
    app = FormulaApp()
    original_execute = app.Execute

    def execute_with_wrong_mode(script):
        result = original_execute(script)
        app.sheet.Columns.Item(2).recalculate_mode = 2
        return result

    app.Execute = execute_with_wrong_mode
    plan = build_column_formula_plan(
        worksheet_ref="[Book1]Data",
        column="C",
        formula="col(A)*col(B)",
        before_script="double scale=1;",
        row_start=0,
        row_end=2,
        recalculate_mode="auto",
    )

    with pytest.raises(NativeValidationError) as captured:
        execute_column_formula_plan(app, app.sheet.Columns.Item(2), plan)

    assert captured.value.code == "COLUMN_FORMULA_UNCONFIRMED"


def test_controller_sets_formula_and_returns_representative_value_readback():
    app = FormulaApp()
    result = owned_controller(app).set_column_formula(
        worksheet_ref="[Book1]Data",
        column="C",
        formula="col(A)*col(B)",
        before_script="double scale=1;",
        row_start=0,
        row_end=2,
        recalculate_mode="auto",
    )

    assert result.success is True
    assert result.data["metadata_verified"] is True
    assert result.data["value_readback_verified"] is True
    assert result.data["value_readback"] == [10.0, 40.0, 90.0]
    assert result.data["worksheet_ref"] == "[Book1]Data"
    assert result.data["column_ref"] == "[Book1]Data!C"


def test_controller_appends_the_next_formula_column_when_it_does_not_exist():
    app = TransformApp()

    result = owned_controller(app).set_column_formula(
        worksheet_ref="[Book1]Data",
        column="C",
        formula="col(A)*col(B)",
        recalculate_mode="auto",
    )

    assert result.success is True
    assert app.sheet.Cols == 3
    assert result.data["column_ref"] == "[Book1]Data!C"
    assert result.data["value_readback"] == [10.0, 40.0, 90.0]


def test_calculated_column_transform_defaults_to_native_formula_without_block_write():
    app = TransformApp()
    result = owned_controller(app).transform_worksheet(
        source_ref="[Book1]Data",
        destination_ref="[Book1]Data",
        action="calculated_column",
        options={
            "name": "product",
            "left": "A",
            "operator": "multiply",
            "right": "B",
        },
    )

    assert result.success is True
    assert result.data["execution_mode"] == "origin_native"
    assert result.data["formula"] == "col(A)*col(B)"
    assert result.data["column_ref"] == "[Book1]Data!C"
    assert result.data["column_label"] == "product"
    assert result.data["value_readback"] == [10.0, 40.0, 90.0]
    assert app.sheet.set_data_calls == []
    assert app.scripts == [
        'csetvalue col:=[Book1]Data!C formula:="col(A)*col(B)" '
        'script:="" recalculate:=1;'
    ]


def test_native_calculated_column_requires_same_source_and_destination():
    result = owned_controller(TransformApp()).transform_worksheet(
        source_ref="[Book1]Data",
        destination_ref="[Book1]Other",
        action="calculated_column",
        options={
            "name": "product",
            "left": "A",
            "operator": "multiply",
            "right": "B",
        },
    )

    assert result.success is False
    assert result.error_code == "NATIVE_CALCULATED_COLUMN_REQUIRES_SAME_WORKSHEET"
