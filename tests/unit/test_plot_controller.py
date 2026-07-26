from origin_com_automation.com.origin_api import OriginController


class InlineWorker:
    def submit(self, fn, *, timeout=None):
        return fn()


class Column:
    def __init__(self, index):
        self.index = index

    def GetDatasetName(self):
        return f"Book1_{chr(ord('A') + self.index)}"


class Columns:
    def Item(self, index):
        return Column(index)


class Sheet:
    Columns = Columns()

    def FindCol(self, name, start, case_sensitive):
        return int(name)


class DataRange:
    def __init__(self):
        self.ranges = []

    def Add(self, designation, sheet, r1, c1, r2, c2):
        self.ranges.append((designation, c1))


class DataPlots:
    def __init__(self):
        self.added = []
        self.items = []

    @property
    def Count(self):
        return len(self.items)

    def Item(self, index):
        return self.items[index]

    def Add(self, data_range, plot_type):
        self.added.append((data_range, plot_type))
        plot = ExistingPlot()
        self.items.append(plot)
        return plot


class ExistingPlot:
    def __init__(self):
        self.destroyed = False

    def Destroy(self):
        self.destroyed = True
        return True

    def GetDatasetName(self):
        return "Book1_B"


class Layer:
    def __init__(self):
        self.DataPlots = DataPlots()
        self.commands = []

    def Execute(self, command):
        self.commands.append(command)


class Layers:
    def __init__(self):
        self.items = [Layer()]

    def Item(self, index):
        return self.items[index]

    def Add(self):
        layer = Layer()
        self.items.append(layer)
        return object()


class GraphPage:
    def __init__(self):
        self.Layers = Layers()


class GraphPages:
    def __init__(self, page):
        self.page = page

    def Item(self, name):
        return self.page


class PlotApp:
    def __init__(self):
        self.Visible = 0
        self.sheet = Sheet()
        self.page = GraphPage()
        self.GraphPages = GraphPages(self.page)

    def FindWorksheet(self, name):
        return self.sheet

    def CreatePage(self, page_type, name, template, option):
        return name or "Graph1"

    def FindGraphLayer(self, name):
        if name.startswith("["):
            index = int(name.split("]", 1)[1]) - 1
            return self.page.Layers.Item(index)
        return self.page.Layers.Item(0)

    def NewDataRange(self):
        return DataRange()

    def Exit(self):
        return True


def test_multi_layer_plot_creates_one_layer_per_y_column():
    app = PlotApp()
    snapshots = iter([set(), {101}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success

    result = controller.create_plot(
        worksheet_name="Book1",
        graph_type="multi_layer",
        x_column=0,
        y_columns=[1, 2],
        graph_name="Graph1",
    )

    assert result.success is True
    assert result.data["layers_created"] == 2
    assert len(app.page.Layers.items) == 2
    assert app.page.Layers.items[0].DataPlots.added[0][0].ranges == [("X", 0), ("Y", 1)]
    assert app.page.Layers.items[1].DataPlots.added[0][0].ranges == [("X", 0), ("Y", 2)]


def test_loglog_plot_uses_origin_2024_log10_axis_values():
    app = PlotApp()
    snapshots = iter([set(), {101}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success

    result = controller.create_plot(
        worksheet_name="Book1",
        graph_type="loglog",
        x_column=0,
        y_columns=[1],
        graph_name="Graph1",
    )

    assert result.success is True
    command = app.page.Layers.items[0].commands[-1]
    assert "layer.x.type=2;" in command
    assert "layer.y.type=2;" in command


def test_create_plot_rejects_options_it_cannot_apply():
    app = PlotApp()
    snapshots = iter([set(), {101}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success

    result = controller.create_plot(
        worksheet_name="Book1",
        graph_type="line",
        x_column=0,
        y_columns=[1],
        options={"ignored_option": True},
    )

    assert result.success is False
    assert result.error_code == "INVALID_GRAPH_REQUEST"


def test_scatter_plot_can_bind_a_label_column_without_helper_worksheet():
    app = PlotApp()
    snapshots = iter([set(), {101}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success

    result = controller.create_plot(
        worksheet_name="Book1",
        graph_type="scatter",
        x_column=0,
        y_columns=[1],
        label_column=2,
        graph_name="Graph1",
    )

    assert result.success is True
    assert app.page.Layers.items[0].DataPlots.added[0][0].ranges == [
        ("X", 0),
        ("Y", 1),
    ]
    command = "".join(app.page.Layers.items[0].commands)
    assert "set Book1_B -q 1;" in command
    assert "set Book1_B -qm 5;" in command
    assert "set Book1_B -j -qms %(Book1_C[i]$);" in command
    assert "set Book1_B -qm Book1_C;" not in command
    assert result.data["label_column"] == 2


def test_configure_graph_applies_ranges_ticks_titles_legend_and_plot_styles():
    app = PlotApp()
    snapshots = iter([set(), {101}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success

    result = controller.configure_graph(
        graph_name="[Graph1]1",
        options={
            "x_min": 0,
            "x_max": 10,
            "x_tick_step": 2,
            "y_scale": "log10",
            "x_title": "Gate voltage (V)",
            "legend": True,
            "plot_styles": [
                {"plot_index": 1, "color_index": 4, "line_connection": "straight"}
            ],
        },
    )

    command = app.page.Layers.items[0].commands[-1]
    assert result.success is True
    assert "layer.x.from=0.0;" in command
    assert "layer.x.to=10.0;" in command
    assert "layer.x.inc=2.0;" in command
    assert "layer.y.type=2;" in command
    assert 'label -xb "Gate voltage (V)";' in command
    assert "legend;" in command
    assert "set %(1,@D) -c 4;" in command
    assert "set %(1,@D) -l 1;" in command


def test_configure_graph_rejects_unknown_options():
    app = PlotApp()
    snapshots = iter([set(), {101}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success

    result = controller.configure_graph(graph_name="Graph1", options={"colour": "blue"})

    assert result.success is False
    assert result.error_code == "INVALID_GRAPH_OPTIONS"


def test_configure_graph_can_rebind_structured_data_columns():
    app = PlotApp()
    old_plot = ExistingPlot()
    app.page.Layers.items[0].DataPlots.items.append(old_plot)
    snapshots = iter([set(), {101}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success

    result = controller.configure_graph(
        graph_name="Graph1",
        options={
            "data_binding": {
                "worksheet_name": "Book1",
                "x_column": 0,
                "y_columns": [1, 2],
                "plot_type": "line",
            }
        },
    )

    plots = app.page.Layers.items[0].DataPlots
    assert result.success is True
    assert old_plot.destroyed is True
    assert len(plots.added) == 2
    assert plots.added[0][0].ranges == [("X", 0), ("Y", 1)]
    assert plots.added[1][0].ranges == [("X", 0), ("Y", 2)]


def test_configure_graph_rebinds_one_plot_to_x_y_and_label_columns():
    app = PlotApp()
    old_plot = ExistingPlot()
    app.page.Layers.items[0].DataPlots.items.append(old_plot)
    snapshots = iter([set(), {101}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success

    result = controller.configure_graph(
        graph_name="Graph1",
        options={
            "data_binding": {
                "worksheet_name": "Book1",
                "x_column": 0,
                "y_columns": [1],
                "label_column": 2,
                "plot_type": "scatter",
            }
        },
    )

    plot_range = app.page.Layers.items[0].DataPlots.added[0][0]
    assert result.success is True
    assert plot_range.ranges == [("X", 0), ("Y", 1)]
    command = "".join(app.page.Layers.items[0].commands)
    assert "set Book1_B -q 1;" in command
    assert "set Book1_B -qm 5;" in command
    assert "set Book1_B -j -qms %(Book1_C[i]$);" in command
    assert "set Book1_B -qm Book1_C;" not in command


def test_configure_graph_does_not_destroy_a_plot_reused_for_the_same_xy_binding():
    class ReusingDataPlots(DataPlots):
        def Add(self, data_range, plot_type):
            self.added.append((data_range, plot_type))
            return self.items[0]

    app = PlotApp()
    old_plot = ExistingPlot()
    plots = ReusingDataPlots()
    plots.items.append(old_plot)
    app.page.Layers.items[0].DataPlots = plots
    snapshots = iter([set(), {101}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
    )
    assert controller.start(progid="Origin.Application").success

    result = controller.configure_graph(
        graph_name="Graph1",
        options={
            "data_binding": {
                "worksheet_name": "Book1",
                "x_column": 0,
                "y_columns": [1],
                "label_column": 2,
                "plot_type": "scatter",
            }
        },
    )

    assert result.success is True
    assert old_plot.destroyed is False
    assert plots.Count == 1
    assert plots.added[0][0].ranges == [("X", 0), ("Y", 1)]
