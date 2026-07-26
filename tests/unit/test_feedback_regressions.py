from __future__ import annotations

import re
from hashlib import sha256
from pathlib import Path

import pytest

from origin_com_automation.com.origin_api import (
    OriginController,
    _categorical_style_commands,
    _graph_configuration_commands,
    _verify_categorical_legend,
)
from origin_com_automation.com.errors import LabTalkExecutionError


LEGENDCAT_DEFAULT_COMMAND = "legendcat mode:=2 combine:=1 showall:=0;"
LEGENDCAT_SHOW_ALL_COMMAND = "legendcat mode:=2 combine:=1 showall:=1;"


class InlineWorker:
    def submit(self, fn, *, timeout=None):
        return fn()


class Column:
    def __init__(self, values, *, data_format=0, name="A", long_name=""):
        self.values = list(values)
        self.DataFormat = data_format
        self.Name = name
        self.LongName = long_name
        self.calls = []

    def GetData(self, data_format, start, end, *optional):
        self.calls.append((data_format, start, end, optional))
        values = self.values[start : None if end == -1 else end + 1]
        if data_format == 8:
            return tuple("" if value is None else str(value) for value in values)
        return tuple(values)


class Columns:
    def __init__(self, items):
        self.items = items
        self.Count = len(items)

    def Item(self, index):
        return self.items[index]


class MixedWorksheet:
    def __init__(self):
        self.Rows = 26
        self.Cols = 4
        self.Columns = Columns(
            [
                Column([None] * 25 + [80.0], name="A", long_name="Lch"),
                Column([None] * 25 + [950.0], name="B", long_name="Ion"),
                Column(
                    [None] * 25 + ["this work"],
                    data_format=1,
                    name="C",
                    long_name="Plot label",
                ),
                Column(
                    ["1L"] * 12
                    + ["2L"] * 11
                    + ["other", "Lch uncertain", "this work"],
                    data_format=1,
                    name="I",
                    long_name="Category",
                ),
            ]
        )
        self.get_data_calls = []

    def GetData(self, r1, c1, r2, c2, data_format):
        self.get_data_calls.append((r1, c1, r2, c2, data_format))
        end_row = self.Rows - 1 if r2 == -1 else r2
        end_col = self.Cols - 1 if c2 == -1 else c2
        rows = []
        for row in range(r1, end_row + 1):
            result_row = []
            for col in range(c1, end_col + 1):
                value = self.Columns.Item(col).values[row]
                if data_format == 2 and isinstance(value, str):
                    value = float(row + 1)
                elif data_format == 4:
                    value = "" if value is None else str(value)
                result_row.append(value)
            rows.append(tuple(result_row))
        return tuple(rows)


class DataApp:
    Version = "10.1.0.178"

    def __init__(self):
        self.Visible = None
        self.sheet = MixedWorksheet()
        self.numeric_reads = []
        self.string_reads = []
        self.lt_strings = {"empty": "", "label": "this work", "warning": "be careful"}

    def FindWorksheet(self, name):
        return self.sheet

    def LTVar(self, name):
        self.numeric_reads.append(name)
        return 42

    def LTStr(self, name):
        self.string_reads.append(name)
        return self.lt_strings.get(name, "")

    def Execute(self, script):
        return True

    def Exit(self):
        return True


def started_controller(app):
    snapshots = iter([set(), {101}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success
    return controller


def test_origin_2024_axis_scale_mapping_is_not_zero_based():
    expected = {"linear": 0, "log10": 2, "ln": 8, "log2": 9}

    for scale, origin_value in expected.items():
        commands = _graph_configuration_commands({"x_scale": scale}, None)
        assert commands == [f"layer.x.type={origin_value};"]


def test_read_worksheet_auto_preserves_mixed_text_and_numeric_values():
    app = DataApp()
    controller = started_controller(app)

    result = controller.read_worksheet(
        "[WSe2Benchmark]Data",
        r1=25,
        c1=0,
        r2=25,
        c2=2,
        data_format="auto",
    )

    assert result.success is True
    assert result.data["data_format"] == "auto"
    assert result.data["values"] == [[80.0, 950.0, "this work"]]
    assert app.sheet.get_data_calls == [(25, 0, 25, 2, 0)]


def test_read_worksheet_supports_numeric_string_variant_and_category_labels():
    app = DataApp()
    controller = started_controller(app)

    numeric = controller.read_worksheet("Data", r1=25, c1=0, r2=25, c2=2, data_format="numeric")
    string = controller.read_worksheet("Data", r1=25, c1=0, r2=25, c2=2, data_format="string")
    variant = controller.read_worksheet("Data", r1=25, c1=0, r2=25, c2=2, data_format="variant")
    categories = controller.read_worksheet(
        "Data", r1=0, c1=3, r2=25, c2=3, data_format="categorical_label"
    )

    assert numeric.data["values"] == [[80.0, 950.0, 26.0]]
    assert string.data["values"] == [["80.0", "950.0", "this work"]]
    assert variant.data["values"] == [[80.0, 950.0, "this work"]]
    assert [row[0] for row in categories.data["values"]].count("1L") == 12
    assert [row[0] for row in categories.data["values"]][-1] == "this work"
    assert app.sheet.Columns.Item(3).calls == [(8, 0, 25, ())]


def test_labtalk_reads_explicit_numeric_and_string_variables_without_guessing():
    app = DataApp()
    controller = started_controller(app)

    result = controller.execute_labtalk(
        script='empty$=""; label$="this work"; n=42;',
        result_numeric_variables=["n"],
        result_string_variables=["empty", "label"],
        warning_variable="warning",
    )

    assert result.success is True
    assert result.data["numeric_output"] == {"n": 42}
    assert result.data["string_output"] == {"empty": "", "label": "this work"}
    assert result.data["output"] == {"n": 42, "empty": "", "label": "this work"}
    assert app.numeric_reads == ["n"]
    assert app.string_reads == ["empty", "label", "warning"]
    assert result.warnings == ["be careful"]


def test_owned_exclusive_request_fails_instead_of_silently_downgrading():
    app = DataApp()
    dispatch_calls = []
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: dispatch_calls.append((progid, attach)) or app,
        process_snapshot=lambda: {55},
    )

    result = controller.start(
        progid="Origin.Application",
        visible=False,
        attach=False,
        exclusive=True,
    )

    assert result.success is False
    assert result.error_code == "EXCLUSIVE_REQUIRES_ATTACH"
    assert dispatch_calls == []


def test_owned_process_start_reports_dispatch_provenance_and_observed_pid():
    app = DataApp()
    snapshots = iter([{55}, {55, 101}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )

    result = controller.start(progid="Origin.Application", visible=False, attach=False)

    assert result.success is True
    assert result.data["exclusive_requested"] is False
    assert result.data["exclusive"] is False
    assert result.data["exclusive_mode"] is None
    assert result.data["process_isolated"] is True
    assert result.data["activation_mode"] == "dispatch_ex_fresh_instance"
    assert result.data["ownership_basis"] == "Origin.Application DispatchEx fresh-instance contract"
    assert result.data["pids_before"] == [55]
    assert result.data["pids_after"] == [55, 101]
    assert result.data["new_pids"] == [101]
    assert result.data["observed_new_pid"] == 101
    assert result.data["pid_binding_confirmed"] is False
    assert "confirmed_owned_pid" not in result.data


class SaveApp(DataApp):
    IsModified = False

    def __init__(self):
        super().__init__()
        self.loads = []
        self.saves = []
        self.new_projects = 0

    def Load(self, path, readonly):
        self.loads.append((str(Path(path).resolve()), readonly))
        return True

    def Save(self, path):
        path = Path(path)
        self.saves.append(str(path.resolve()))
        path.write_bytes(b"validated-replacement-project" + b"x" * 128)
        return True

    def Run(self):
        return True

    def NewProject(self):
        self.new_projects += 1
        return True


def test_explicit_source_replace_uses_verified_candidate_and_reports_hashes(tmp_path):
    app = SaveApp()
    controller = started_controller(app)
    source = tmp_path / "source.opju"
    original = b"original-project" + b"o" * 128
    source.write_bytes(original)
    working = tmp_path / "working.opju"
    assert controller.open_project(source_path=str(source), working_copy_path=str(working)).success

    result = controller.save_and_replace_source(
        source_path=str(source),
        overwrite=True,
        allow_source_overwrite=True,
        expected_source_sha256=sha256(original).hexdigest(),
    )

    assert result.success is True
    assert result.data["before"]["sha256"] == sha256(original).hexdigest()
    assert result.data["after"]["sha256"] == sha256(source.read_bytes()).hexdigest()
    assert result.data["before"]["sha256"] != result.data["after"]["sha256"]
    assert result.data["candidate_reopen_verified"] is True
    assert result.data["atomic_replace"] is True
    assert result.data["active_project_open"] is False
    backup = Path(result.data["backup_path"])
    assert backup.is_file()
    assert sha256(backup.read_bytes()).hexdigest() == sha256(original).hexdigest()
    assert app.new_projects >= 2
    assert any(Path(path).name.startswith(".source.codex-candidate-") for path, _ in app.loads)
    assert app.loads[-1][0] != str(source.resolve())


def test_source_replace_requires_all_high_risk_confirmations(tmp_path):
    app = SaveApp()
    controller = started_controller(app)
    source = tmp_path / "source.opju"
    original = b"original-project" + b"o" * 128
    source.write_bytes(original)
    assert controller.open_project(source_path=str(source)).success

    result = controller.save_and_replace_source(
        source_path=str(source),
        overwrite=True,
        allow_source_overwrite=False,
        expected_source_sha256=sha256(original).hexdigest(),
    )

    assert result.success is False
    assert result.error_code == "SOURCE_REPLACE_CONFIRMATION_REQUIRED"
    assert source.read_bytes() == original
    assert app.saves == []


class GraphObject:
    def __init__(self, name, text=""):
        self.Name = name
        self.Text = text


class MutableCollection:
    def __init__(self, items=None):
        self.items = list(items or [])

    @property
    def Count(self):
        return len(self.items)

    def Item(self, index):
        if isinstance(index, str):
            return next(item for item in self.items if item.Name == index)
        return self.items[index]


class StyledPlot:
    Name = "WSe2Benchmark_B"
    TypeName = "Unknow"
    Range = "[Ion_vs_Lch]1!Plot(1)"

    def GetDatasetName(self):
        return "WSe2Benchmark_B"

    def GetNumProp(self, name):
        return 1 if name == "label.show" else 0

    def GetStrProp(self, name):
        return "WSe2Benchmark_C" if name == "label.form" else ""


class StyleColumn(Column):
    def __init__(self, values, *, index, name, long_name, designation):
        super().__init__(values, data_format=1 if any(isinstance(v, str) for v in values) else 0, name=name, long_name=long_name)
        self.Index = index
        self.Units = ""
        self.Comments = ""
        self.PlotDesignation = designation

    def GetDatasetName(self):
        return f"WSe2Benchmark_{self.Name}"


class StyleSheet:
    Name = "Data"
    LongName = "Data"
    Index = 0
    Rows = 3
    Cols = 4

    def __init__(self):
        self.Columns = Columns(
            [
                StyleColumn([10, 20, 30], index=0, name="A", long_name="Lch", designation=3),
                StyleColumn([100, 200, 300], index=1, name="B", long_name="Ion", designation=0),
                StyleColumn(["a", "b", "c"], index=2, name="C", long_name="Plot label", designation=4),
                StyleColumn(["1L", "2L", "1L"], index=3, name="I", long_name="Category", designation=1),
            ]
        )
        self.DataObjectBases = self.Columns

    def FindCol(self, name, start, case_sensitive):
        lookup = {column.Name: column.Index for column in self.Columns.items}
        lookup.update({column.LongName: column.Index for column in self.Columns.items})
        return type("Found", (), {"Index": lookup[name]})()


class StyleLayer:
    Name = "Layer1"
    LongName = ""
    Index = 0

    def __init__(self):
        self.DataPlots = MutableCollection([StyledPlot()])
        self.DataObjectBases = MutableCollection()
        self.GraphObjects = MutableCollection()
        self.commands = []

    def Execute(self, command):
        self.commands.append(command)
        if "label -r CategoryKey;" in command:
            self.GraphObjects.items = [item for item in self.GraphObjects.items if item.Name != "CategoryKey"]
        if "label -r Legend;" in command:
            self.GraphObjects.items = [item for item in self.GraphObjects.items if item.Name != "Legend"]
        if command.strip() in {LEGENDCAT_DEFAULT_COMMAND, LEGENDCAT_SHOW_ALL_COMMAND}:
            self.GraphObjects.items = [item for item in self.GraphObjects.items if item.Name != "Legend"]
            self.GraphObjects.items.append(GraphObject("Legend", "1L\r\n2L"))
        return True


class StylePage:
    def __init__(self, name, layer, *, type_name):
        self.Name = name
        self.LongName = name
        self.TypeName = type_name
        self.PEPath = f"/{name}"
        self.Layers = MutableCollection([layer])


class StyleApp(DataApp):
    def __init__(self):
        super().__init__()
        self.sheet = StyleSheet()
        self.layer = StyleLayer()
        self.workbook = StylePage("WSe2Benchmark", self.sheet, type_name="Worksheet")
        self.graph = StylePage("Ion_vs_Lch", self.layer, type_name="Graph")
        self.WorksheetPages = MutableCollection([self.workbook])
        self.GraphPages = MutableCollection([self.graph])
        self.MatrixPages = MutableCollection()

    def FindWorksheet(self, name):
        return self.sheet

    def FindGraphLayer(self, name):
        return self.layer


def category_options():
    return {
        "plot_index": 1,
        "category_column": "[WSe2Benchmark]Data!Col(Category)",
        "categories": {
            "1L": {"color": "#2878B5", "shape": "circle", "fill": "solid", "size": 10},
            "2L": {"color": "#E76F51", "shape": "square", "fill": "open", "size": 12},
        },
    }


def test_structured_category_style_applies_stable_per_point_properties_in_order():
    app = StyleApp()
    controller = started_controller(app)

    result = controller.configure_graph(
        graph_name="Ion_vs_Lch",
        options={"categorical_style": category_options()},
    )

    assert result.success is True
    command = app.layer.commands[-1]
    assert "set WSe2Benchmark_I -dc 1;" in command
    assert "set WSe2Benchmark_B -ksn WSe2Benchmark_I;" in command
    assert "set WSe2Benchmark_B -c WSe2Benchmark_I;" in command
    assert "set WSe2Benchmark_B -cn WSe2Benchmark_I;" not in command
    assert "set WSe2Benchmark_B -csfn WSe2Benchmark_I;" in command
    first_point = (
        'set WSe2Benchmark_B 1 -k 2;'
        'set WSe2Benchmark_B 1 -kf 0;'
        'set WSe2Benchmark_B 1 -c color("#2878B5");'
        'set WSe2Benchmark_B 1 -csf color("#2878B5");'
        'set WSe2Benchmark_B 1 -z 10.0;'
    )
    assert first_point in command
    assert result.data["categorical_style"]["category_counts"] == {"1L": 2, "2L": 1}


def test_categorical_style_uses_bound_y_column_when_plot_reports_label_dataset():
    class LabelReportingPlot(StyledPlot):
        def GetDatasetName(self):
            return "WSe2Benchmark_C"

    app = StyleApp()
    app.layer.DataPlots = MutableCollection([LabelReportingPlot()])
    app.graph.Layers = MutableCollection([app.layer])

    commands, result = _categorical_style_commands(
        app,
        app.layer,
        category_options(),
        {
            "worksheet_name": "[WSe2Benchmark]Data",
            "x_column": "A",
            "y_columns": ["B"],
            "label_column": "C",
            "plot_type": "scatter",
        },
    )

    assert result["plot_dataset"] == "WSe2Benchmark_B"
    assert any("set WSe2Benchmark_B -ksn WSe2Benchmark_I;" in command for command in commands)
    assert all("set WSe2Benchmark_C" not in command for command in commands)


def test_categorical_legend_uses_native_legendcat_idempotently():
    app = StyleApp()
    controller = started_controller(app)
    options = {
        "categorical_style": category_options(),
        "legend": {
            "mode": "categorical",
            "source": "plot_style_mapping",
            "position": "top_right",
            "font_size": 9,
            "border": False,
            "background": "transparent",
            "replace_existing": True,
        },
    }

    first = controller.configure_graph(graph_name="Ion_vs_Lch", options=options)
    second = controller.configure_graph(graph_name="Ion_vs_Lch", options=options)

    assert first.success is True and second.success is True
    assert [item.Name for item in app.layer.GraphObjects.items] == ["Legend"]
    legend = app.layer.GraphObjects.items[0]
    assert legend.Text.splitlines() == ["1L", "2L"]
    command = "".join(app.layer.commands)
    assert "label -r CategoryKey;" in command
    assert "label -r Legend;" in command
    assert LEGENDCAT_DEFAULT_COMMAND in command
    assert "Legend.text$=" not in command
    assert "Legend.fsize=9.0;" in command
    assert "Legend.background=0;" in command
    assert sum(part.strip() == LEGENDCAT_DEFAULT_COMMAND for part in app.layer.commands) == 2


def test_categorical_legend_explicitly_enables_show_all_categories():
    app = StyleApp()
    controller = started_controller(app)

    result = controller.configure_graph(
        graph_name="Ion_vs_Lch",
        options={
            "categorical_style": category_options(),
            "legend": {
                "mode": "categorical",
                "source": "plot_style_mapping",
                "show_all_categories": True,
                "replace_existing": True,
            },
        },
    )

    assert result.success is True, result.to_dict()
    assert sum(
        command.strip() == LEGENDCAT_SHOW_ALL_COMMAND for command in app.layer.commands
    ) == 1


def test_internal_legend_placeholder_does_not_count_as_a_populated_legend():
    class NativeLegendLayer:
        def __init__(self):
            self.GraphObjects = MutableCollection([GraphObject("_232")])
            self.commands = []

        def Execute(self, command):
            self.commands.append(command)
            return True

    layer = NativeLegendLayer()

    with pytest.raises(LabTalkExecutionError, match="populated native categorical Legend"):
        _verify_categorical_legend(object(), layer, replace_existing=True)


def test_native_categorical_legend_can_be_resolved_by_collection_name():
    class NamedLegendCollection(MutableCollection):
        def __init__(self):
            super().__init__([GraphObject("_232")])
            self.legend = GraphObject("Legend", "\\l(1,m1,4) 1L\r\n\\l(1,m2,4) 2L")

        def Item(self, index):
            if isinstance(index, str) and index.casefold() == "legend":
                return self.legend
            return super().Item(index)

    class NativeLegendLayer:
        GraphObjects = NamedLegendCollection()

    _verify_categorical_legend(object(), NativeLegendLayer(), replace_existing=True)


def test_native_categorical_legend_can_be_verified_through_labtalk_strings():
    class InternalLegendLayer:
        def __init__(self):
            self.GraphObjects = MutableCollection([GraphObject("_232")])
            self.commands = []
            self.variables = {}

        def Execute(self, command):
            self.commands.append(command)
            for variable, field in re.findall(
                r'(cxlegend[0-9a-f]+(?:name|text))\$="%\(Legend\.(name|text)\$\)";',
                command,
            ):
                self.variables[variable] = {
                    "name": "_232",
                    "text": "\\l(1,m1,4) 1L\r\n\\l(1,m2,4) 2L",
                }[field]
            return True

        def LTStr(self, name):
            return self.variables.get(name, "")

    layer = InternalLegendLayer()

    _verify_categorical_legend(
        object(),
        layer,
        replace_existing=True,
        expected_entries=2,
    )

    command = "".join(layer.commands)
    assert '="%(Legend.name$)";' in command
    assert '="%(Legend.text$)";' in command


def test_categorical_legend_runs_after_category_state_reaches_worker_boundary():
    class BoundaryLegendLayer(StyleLayer):
        def __init__(self):
            super().__init__()
            self.pending_style = False
            self.style_committed = False
            self.variables = {}

        def commit_pending(self):
            if self.pending_style:
                self.style_committed = True

        def Execute(self, command):
            self.commands.append(command)
            if "set WSe2Benchmark_I -dc 1;" in command:
                self.pending_style = True
            if "label -r CategoryKey;" in command:
                self.GraphObjects.items = [
                    item for item in self.GraphObjects.items if item.Name != "CategoryKey"
                ]
            if "label -r Legend;" in command:
                self.GraphObjects.items = [
                    item for item in self.GraphObjects.items if item.Name != "Legend"
                ]
            if command.strip() == LEGENDCAT_DEFAULT_COMMAND and self.style_committed:
                self.GraphObjects.items = [
                    item for item in self.GraphObjects.items if item.Name != "Legend"
                ]
                self.GraphObjects.items.append(GraphObject("Legend", "1L\r\n2L"))
            for variable, field in re.findall(
                r'(cxlegend[0-9a-f]+(?:name|text))\$="%\(Legend\.(name|text)\$\)";',
                command,
            ):
                self.variables[variable] = {
                    "name": "Legend" if self.style_committed else "",
                    "text": "1L\r\n2L" if self.style_committed else "",
                }[field]
            return True

        def LTStr(self, name):
            return self.variables.get(name, "")

    class BoundaryWorker(InlineWorker):
        def __init__(self, layer):
            self.layer = layer

        def submit(self, fn, *, timeout=None):
            result = fn()
            self.layer.commit_pending()
            return result

    app = StyleApp()
    app.layer = BoundaryLegendLayer()
    app.graph.Layers = MutableCollection([app.layer])
    snapshots = iter([set(), {101}])
    controller = OriginController(
        worker=BoundaryWorker(app.layer),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success

    result = controller.configure_graph(
        graph_name="Ion_vs_Lch",
        options={
            "categorical_style": category_options(),
            "legend": {
                "mode": "categorical",
                "source": "plot_style_mapping",
                "replace_existing": True,
            },
        },
    )

    assert result.success is True, result.to_dict()
    assert sum(command.strip() == LEGENDCAT_DEFAULT_COMMAND for command in app.layer.commands) == 1


def test_categorical_legend_is_created_after_category_styles_are_committed():
    class RefreshSensitiveLegendLayer(StyleLayer):
        def Execute(self, command):
            return super().Execute(command)

    app = StyleApp()
    app.layer = RefreshSensitiveLegendLayer()
    app.graph.Layers = MutableCollection([app.layer])
    controller = started_controller(app)

    result = controller.configure_graph(
        graph_name="Ion_vs_Lch",
        options={
            "categorical_style": category_options(),
            "legend": {
                "mode": "categorical",
                "source": "plot_style_mapping",
                "position": "top_right",
                "font_size": 9,
                "border": False,
                "background": "transparent",
                "replace_existing": True,
            },
        },
    )

    assert result.success is True, result.to_dict()
    style_index = next(
        index
        for index, command in enumerate(app.layer.commands)
        if "set WSe2Benchmark_I -dc 1;" in command
    )
    legend_index = next(
        index
        for index, command in enumerate(app.layer.commands)
        if command.strip() == LEGENDCAT_DEFAULT_COMMAND
    )
    format_index = next(
        index for index, command in enumerate(app.layer.commands) if "Legend.fsize" in command
    )
    assert style_index < legend_index < format_index
    assert sum(command.strip() == LEGENDCAT_DEFAULT_COMMAND for command in app.layer.commands) == 1
    assert [item.Name for item in app.layer.GraphObjects.items] == ["Legend"]


def test_list_objects_normalizes_dataplot_type_and_resolves_source_columns():
    app = StyleApp()
    controller = started_controller(app)

    result = controller.list_objects()

    plot = next(item for item in result.data["data_sources"] if item["collection"] == "DataPlots")
    assert plot["type"] == "DataPlot"
    assert plot["graph"] == "Ion_vs_Lch"
    assert plot["layer"] == 1
    assert plot["dataset_name"] == "WSe2Benchmark_B"
    assert plot["source_workbook"] == "WSe2Benchmark"
    assert plot["source_worksheet"] == "Data"
    assert plot["x_column"] == "A"
    assert plot["x_long_name"] == "Lch"
    assert plot["y_column"] == "B"
    assert plot["y_long_name"] == "Ion"
    assert plot["label_column"] == "C"
    assert plot["label_long_name"] == "Plot label"


def test_list_objects_fails_closed_when_a_root_com_collection_is_unreadable():
    class RpcUnavailableError(RuntimeError):
        hresult = -2147023174

    class BrokenAuditApp(DataApp):
        @property
        def WorksheetPages(self):
            raise RpcUnavailableError("RPC server unavailable")

    app = BrokenAuditApp()
    controller = started_controller(app)

    result = controller.list_objects()

    assert result.success is False
    assert result.error_code == "RPC_SERVER_UNAVAILABLE"
    assert result.warnings == ["Retried once after RPC_SERVER_UNAVAILABLE"]


class UnlabelledPlot(StyledPlot):
    def GetNumProp(self, name):
        return 0

    def GetStrProp(self, name):
        return ""


class SubstitutionLayer(StyleLayer):
    def __init__(self, substitutions):
        super().__init__()
        self.DataPlots = MutableCollection([UnlabelledPlot()])
        self.substitutions = substitutions
        self.variables = {}

    def Execute(self, command):
        self.commands.append(command)
        for variable, token in re.findall(r'(cx[0-9a-f]+\d+)\$="([^"]*)";', command):
            self.variables[variable] = self.substitutions.get(token, token)
        return True

    def LTStr(self, name):
        return self.variables.get(name, "")


class CustomLabelPlot(UnlabelledPlot):
    def GetNumProp(self, name):
        return 1 if name == "label.show" else 0


class CustomLabelLayer(SubstitutionLayer):
    def __init__(self, substitutions, custom_format):
        super().__init__(substitutions)
        self.DataPlots = MutableCollection([CustomLabelPlot()])
        self.custom_format = custom_format

    def Execute(self, command):
        result = super().Execute(command)
        for variable in re.findall(
            r"get\s+WSe2Benchmark_B\s+-qms\s+(cxlabel[0-9a-f]+)\$;",
            command,
        ):
            self.variables[variable] = self.custom_format
        return result


def test_list_objects_resolves_custom_text_label_dataset_from_qms():
    app = StyleApp()
    substitutions = {
        "%(1,@W)": "WSe2Benchmark",
        "%(1,@WS)": "Data",
        "%(1X,@D)": "WSe2Benchmark_A",
        "%(1X,@R)": "A",
        "%(1X,@L)": "Lch",
        "%(1Y,@D)": "WSe2Benchmark_B",
        "%(1Y,@R)": "B",
        "%(1Y,@L)": "Ion",
        "%(1L,@D)": "###",
        "%(1L,@R)": "###",
        "%(1L,@L)": "###",
    }
    app.layer = CustomLabelLayer(substitutions, "%(WSe2Benchmark_C[i]$)")
    app.graph.Layers = MutableCollection([app.layer])
    controller = started_controller(app)

    result = controller.list_objects()

    plot = next(item for item in result.data["data_sources"] if item["collection"] == "DataPlots")
    assert plot["label_column"] == "C"
    assert plot["label_long_name"] == "Plot label"
    assert plot["label_dataset_name"] == "WSe2Benchmark_C"
    assert any("get WSe2Benchmark_B -qms" in command for command in app.layer.commands)


def test_list_objects_marks_unmatched_custom_label_dataset_as_unresolved():
    app = StyleApp()
    substitutions = {
        "%(1,@W)": "WSe2Benchmark",
        "%(1,@WS)": "Data",
        "%(1X,@D)": "WSe2Benchmark_A",
        "%(1X,@R)": "A",
        "%(1X,@L)": "Lch",
        "%(1Y,@D)": "WSe2Benchmark_B",
        "%(1Y,@R)": "B",
        "%(1Y,@L)": "Ion",
        "%(1L,@D)": "###",
        "%(1L,@R)": "###",
        "%(1L,@L)": "###",
    }
    app.layer = CustomLabelLayer(substitutions, "%(_missing_label_dataset[i]$)")
    app.graph.Layers = MutableCollection([app.layer])
    controller = started_controller(app)

    result = controller.list_objects()

    plot = next(item for item in result.data["data_sources"] if item["collection"] == "DataPlots")
    assert plot["label_source_status"] == "unresolved"
    assert plot["label_column"] is None
    assert plot["label_long_name"] is None
    assert plot["label_dataset_name"] is None
    assert plot["label_range"] is None


def test_list_objects_normalizes_unavailable_label_substitutions_to_none():
    app = StyleApp()
    substitutions = {
        "%(1,@W)": "WSe2Benchmark",
        "%(1,@WS)": "Data",
        "%(1X,@D)": "WSe2Benchmark_A",
        "%(1X,@R)": "A",
        "%(1X,@L)": "Lch",
        "%(1Y,@D)": "WSe2Benchmark_B",
        "%(1Y,@R)": "B",
        "%(1Y,@L)": "Ion",
        "%(1L,@D)": "###",
        "%(1L,@R)": "% (1L,@R)",
        "%(1L,@L)": "###",
    }
    app.layer = SubstitutionLayer(substitutions)
    app.graph.Layers = MutableCollection([app.layer])
    controller = started_controller(app)

    result = controller.list_objects()

    plot = next(item for item in result.data["data_sources"] if item["collection"] == "DataPlots")
    assert plot["type"] == "DataPlot"
    assert plot["origin_type_name"] == "Unknow"
    assert plot["x_column"] == "A"
    assert plot["x_long_name"] == "Lch"
    assert plot["x_dataset_name"] == "WSe2Benchmark_A"
    assert plot["y_column"] == "B"
    assert plot["y_long_name"] == "Ion"
    assert plot["y_dataset_name"] == "WSe2Benchmark_B"
    assert plot["label_column"] is None
    assert plot["label_long_name"] is None
    assert plot["label_dataset_name"] is None
    assert plot["label_range"] is None
