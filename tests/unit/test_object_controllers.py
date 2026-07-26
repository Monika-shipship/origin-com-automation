from pathlib import Path

from origin_com_automation.com.origin_api import OriginController


class InlineWorker:
    def submit(self, fn, *, timeout=None):
        return fn()


class Collection:
    def __init__(self, items, factory=None):
        self.items = items
        self.factory = factory
        self.Count = len(items)

    def Item(self, index):
        if isinstance(index, str):
            return next(
                item
                for item in self.items
                if index in {getattr(item, "Name", None), getattr(item, "LongName", None)}
            )
        return self.items[index]

    def Add(self):
        item = self.factory() if self.factory else None
        self.items.append(item)
        self.Count = len(self.items)
        return item


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
        self.Name = "MSheet1"
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
        self.Name = "Image1"
        self.LongName = "Image1"
        self.Source = ""
        self.Width = 10
        self.Height = 20

    def Import(self, path):
        self.Source = path
        return True

    def Export(self, path):
        Path(path).write_bytes(b"image-output")
        return True


class Page:
    def __init__(self, name, layer):
        self.Name = name
        self.LongName = name
        self.Layers = Collection([layer])


class ObjectApp:
    Version = "10.1.0.178"

    def __init__(self):
        self.sheets = {
            "[Book1]Data": Sheet([["a", 2], ["b", 1]], ["group", "x"]),
            "[Book1]Out": Sheet([], ["group", "x"]),
        }
        self.matrix = Matrix()
        self.image = ImagePage()
        self.MatrixPages = Collection(
            [], factory=lambda: Page("MBook1", self.matrix)
        )
        self.ImagePages = Collection([], factory=lambda: ImagePage())

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


def test_controller_uses_native_data_connector_when_wrapper_is_absent(tmp_path):
    source = tmp_path / "native.csv"
    source.write_text("x,y\n1,2\n", encoding="utf-8")

    class Book:
        def __init__(self):
            self.connector_type = ""

        def GetStrProp(self, name):
            return self.connector_type if name == "DC.Type" else ""

    class NativeSheet(Sheet):
        def __init__(self):
            super().__init__([[1, 2]], ["x", "y"])
            del self.Connector
            self.Parent = Book()
            self.connected = False
            self.source = ""
            self.refreshes = 0

        def DoMethod(self, name, argument):
            if name == "DC.Import":
                self.refreshes += 1
            return 1

        def Execute(self, script):
            if "wbook.dc.add" in script:
                self.connected = True
                self.Parent.connector_type = "CSV_Connector"
            elif "wbook.dc.remove" in script:
                self.connected = False
            return 1

        def GetNumProp(self, name):
            return 1 if name == "HasDC" and self.connected else 0

        def GetStrProp(self, name):
            return self.source if name == "DC.Source" else ""

        def SetStrProp(self, name, value):
            if name == "DC.Source":
                self.source = value
            return 1

    app = ObjectApp()
    app.sheets["[Book1]Native"] = NativeSheet()
    controller = owned_controller(app)

    created = controller.manage_connector(
        action="create",
        worksheet_ref="[Book1]Native",
        source=str(source),
        connector_type="csv",
    )
    refreshed = controller.manage_connector(
        action="refresh", worksheet_ref="[Book1]Native"
    )
    disconnected = controller.manage_connector(
        action="disconnect", worksheet_ref="[Book1]Native", keep_data=True
    )

    assert created.success and created.data["interface"] == "labtalk_data_connector"
    assert refreshed.success and refreshed.data["refresh_count"] == 2
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


def test_controller_creates_matrix_and_returns_actual_stable_ref():
    controller = owned_controller(ObjectApp())

    result = controller.manage_matrix(action="create", matrix_ref="LiveMatrix")

    assert result.success is True
    assert result.data["matrix_ref"] == "[MBook1]MSheet1"
    assert result.data["requested_ref"] == "LiveMatrix"
    assert result.data["verified"] is True


def test_controller_uses_first_matrix_object_for_real_com_shape():
    app = ObjectApp()

    class TransposedComMatrix(Matrix):
        def GetData(self, r1=0, c1=0, r2=-1, c2=-1):
            return tuple(tuple(item) for item in zip(*self.data, strict=True))

    class NativeMatrixSheet:
        def __init__(self, matrix_object):
            self.MatrixObjects = Collection([matrix_object])

    app.matrix = NativeMatrixSheet(TransposedComMatrix())
    controller = owned_controller(app)

    written = controller.manage_matrix(
        action="write",
        matrix_ref="[MBook1]MSheet1",
        values=[[1, 2], [3, 4]],
    )
    read = controller.manage_matrix(
        action="read", matrix_ref="[MBook1]MSheet1"
    )

    assert written.success is True
    assert written.data["readback_verified"] is True
    assert read.data["values"] == [[1.0, 2.0], [3.0, 4.0]]


def test_controller_image_import_and_export_verify_artifact(tmp_path):
    source = tmp_path / "source.png"
    source.write_bytes(b"input")
    target = tmp_path / "target.png"
    controller = owned_controller(ObjectApp())
    imported = controller.manage_image(action="import", image_ref="Image1", path=str(source))
    exported = controller.manage_image(action="export", image_ref="Image1", path=str(target))
    assert imported.success and imported.data["source"] == str(source.resolve())
    assert exported.success and target.stat().st_size > 0


def test_controller_creates_image_page_through_com_collection():
    controller = owned_controller(ObjectApp())

    result = controller.manage_image(action="create", image_ref="LiveImage")

    assert result.success is True
    assert result.data["image_ref"] == "Image1"
    assert result.data["requested_ref"] == "LiveImage"
