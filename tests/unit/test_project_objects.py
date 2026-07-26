import pytest

from origin_com_automation.com.origin_api import OriginController
from origin_com_automation.objects.project import ProjectObjectError, build_folder_plan, build_note_plan


def test_folder_plan_normalizes_full_project_paths():
    plan = build_folder_plan(action="create", path="/Analysis/Fits")
    assert plan.path == "/Analysis/Fits"
    assert plan.parent_path == "/Analysis"
    assert plan.name == "Fits"


def test_folder_delete_requires_recursive_confirmation_for_nonempty_folder():
    with pytest.raises(ProjectObjectError, match="confirm_recursive"):
        build_folder_plan(
            action="delete", path="/Analysis", nonempty=True, confirm_recursive=False
        )
    plan = build_folder_plan(
        action="delete", path="/Analysis", nonempty=True, confirm_recursive=True
    )
    assert plan.confirm_recursive is True


def test_folder_move_and_rename_require_distinct_destinations():
    with pytest.raises(ProjectObjectError, match="destination"):
        build_folder_plan(action="move", path="/A", destination="/A")
    renamed = build_folder_plan(action="rename", path="/A", destination="B")
    assert renamed.destination == "/B"


def test_note_write_requires_text_and_export_extension(tmp_path):
    with pytest.raises(ProjectObjectError, match="text"):
        build_note_plan(action="write", note_ref="Note1", text=None)
    plan = build_note_plan(
        action="export",
        note_ref="Note1",
        path=str(tmp_path / "note.html"),
        overwrite=False,
    )
    assert plan.path.suffix == ".html"
    with pytest.raises(ProjectObjectError, match="extension"):
        build_note_plan(
            action="export", note_ref="Note1", path=str(tmp_path / "note.pdf")
        )


class InlineWorker:
    def submit(self, fn, *, timeout=None):
        return fn()


class FolderInterface:
    def __init__(self):
        self.paths = {"/"}

    def Create(self, path):
        self.paths.add(path)
        return True

    def Exists(self, path):
        return path in self.paths

    def List(self, path):
        return sorted(item for item in self.paths if item != path and item.startswith(path.rstrip("/") + "/"))

    def Move(self, source, destination):
        self.paths.remove(source)
        self.paths.add(destination)
        return True

    def Delete(self, path, recursive):
        self.paths = {item for item in self.paths if item != path and not item.startswith(path + "/")}
        return True


class Note:
    def __init__(self):
        self.Text = ""
        self.Format = "text"

    def Export(self, path, format):
        from pathlib import Path
        Path(path).write_text(self.Text, encoding="utf-8")
        return True


class ProjectApp:
    Version = "10.1.0.178"

    def __init__(self):
        self.ProjectFolders = FolderInterface()
        self.notes = {"Note1": Note()}

    def FindNotePage(self, ref):
        return self.notes.get(ref)

    def CreateNotePage(self, ref):
        self.notes[ref] = Note()
        return self.notes[ref]


def owned_controller():
    controller = OriginController(worker=InlineWorker())
    controller._app = ProjectApp()
    record = controller.sessions.register(
        progid="Origin.Application", pid=999, owned=True, visible=False
    )
    controller._session_id = record.session_id
    return controller


def test_project_folder_controller_creates_and_relists_path():
    controller = owned_controller()
    result = controller.manage_project_folder(action="create", path="/Analysis")
    listed = controller.manage_project_folder(action="list", path="/")
    assert result.success is True
    assert result.data["verified"] is True
    assert "/Analysis" in listed.data["children"]


def test_note_controller_writes_reads_and_exports(tmp_path):
    controller = owned_controller()
    written = controller.manage_note(action="write", note_ref="Note1", text="result summary")
    output = tmp_path / "note.txt"
    exported = controller.manage_note(action="export", note_ref="Note1", path=str(output))
    assert written.success and written.data["text"] == "result summary"
    assert exported.success and output.read_text(encoding="utf-8") == "result summary"
