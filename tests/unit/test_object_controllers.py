from pathlib import Path

from origin_com_automation.com.origin_api import OriginController


class InlineWorker:
    def submit(self, fn, *, timeout=None):
        return fn()


class Collection:
    def __init__(self, items):
        self.items = items
        self.Count = len(items)

    def Item(self, index):
        return self.items[index]


class Column:
    def __init__(self, name):
        self.Name = name
        self.LongName = name
        self.DataFormat = 0


class Connector:
    def __init__(self):
        self.Source = ""
        self.Type = ""
        self.Connected = False
        self.refreshes = 0

    def Connect(self, source, connector_type, keep_connector):
        self.Source = source
        self.Type = connector_type
        self.Connected = bool(keep_connector)
        return True

    def Refresh(self):
        self.refreshes += 1
        return True

    def Disconnect(self, keep_data):
        self.Connected = False
        self.keep_data = keep_data
        return True


class Sheet:
    def __init__(self, rows, columns):
        self.data = [list(row) for row in rows]
        self.Columns = Collection([Column(name) for name in columns])
        self.Rows = len(rows)
        self.Cols = len(columns)
        self.Connector = Connector()

    def GetData(self, r1, c1, r2, c2, data_format):
        end_row = len(self.data) if r2 == -1 else r2 + 1
        end_col = self.Cols if c2 == -1 else c2 + 1
        return tuple(tuple(row[c1:end_col]) for row in self.data[r1:end_row])

    def SetData(self, values, row, column):
        self.data = [list(item) for item in values]
        self.Rows = len(self.data)
        self.Cols = len(self.data[0]) if self.data else 0
        return True


class Matrix:
    def __init__(self):
        self.data = [[0.0]]
        self.scripts = []

    def SetData(self, values, row, column):
        self.data = [list(item) for item in values]
        return True

    def GetData(self, r1=0, c1=0, r2=-1, c2=-1):
        return tuple(tuple(item) for item in self.data)

    def Execute(self, script):
        self.scripts.append(script)
        return True


class ImagePage:
    def __init__(self):
        self.Source = ""
        self.Width = 10
        self.Height = 20

    def Import(self, path):
        self.Source = path
        return True

    def Export(self, path):
        Path(path).write_bytes(b"image-output")
        return True


class ObjectApp:
    Version = "10.1.0.178"

    def __init__(self):
        self.sheets = {
            "[Book1]Data": Sheet([["a", 2], ["b", 1]], ["group", "x"]),
            "[Book1]Out": Sheet([], ["group", "x"]),
        }
        self.matrix = Matrix()
        self.image = ImagePage()

    def FindWorksheet(self, ref):
        return self.sheets.get(ref)

    def FindMatrixSheet(self, ref):
        return self.matrix if ref == "[MBook1]MSheet1" else None

    def FindImagePage(self, ref):
        return self.image if ref == "Image1" else None


def owned_controller(app):
    controller = OriginController(worker=InlineWorker())
    controller._app = app
    record = controller.sessions.register(
        progid="Origin.Application", pid=321, owned=True, visible=False
    )
    controller._session_id = record.session_id
    return controller


def test_controller_transforms_and_verifies_destination_worksheet():
    app = ObjectApp()
    result = owned_controller(app).transform_worksheet(
        source_ref="[Book1]Data",
        destination_ref="[Book1]Out",
        action="sort",
        options={"by": ["x"], "ascending": True},
    )
    assert result.success is True
    assert result.data["readback_verified"] is True
    assert app.sheets["[Book1]Out"].data == [["b", 1], ["a", 2]]


def test_controller_connector_lifecycle_verifies_state(tmp_path):
    source = tmp_path / "data.csv"
    source.write_text("x,y\n1,2\n", encoding="utf-8")
    controller = owned_controller(ObjectApp())
    created = controller.manage_connector(
        action="create",
        worksheet_ref="[Book1]Data",
        source=str(source),
        connector_type="csv",
        keep_connector=True,
    )
    refreshed = controller.manage_connector(action="refresh", worksheet_ref="[Book1]Data")
    disconnected = controller.manage_connector(
        action="disconnect", worksheet_ref="[Book1]Data", keep_data=True
    )
    assert created.success and created.data["connected"] is True
    assert refreshed.success and refreshed.data["refresh_count"] == 1
    assert disconnected.success and disconnected.data["connected"] is False


def test_controller_matrix_write_reads_back_exact_block():
    controller = owned_controller(ObjectApp())
    result = controller.manage_matrix(
        action="write",
        matrix_ref="[MBook1]MSheet1",
        values=[[1, 2], [3, 4]],
    )
    assert result.success is True
    assert result.data["readback_verified"] is True


def test_controller_image_import_and_export_verify_artifact(tmp_path):
    source = tmp_path / "source.png"
    source.write_bytes(b"input")
    target = tmp_path / "target.png"
    controller = owned_controller(ObjectApp())
    imported = controller.manage_image(action="import", image_ref="Image1", path=str(source))
    exported = controller.manage_image(action="export", image_ref="Image1", path=str(target))
    assert imported.success and imported.data["source"] == str(source.resolve())
    assert exported.success and target.stat().st_size > 0
