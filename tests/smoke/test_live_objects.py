import os
import time

import psutil
import pytest
from PIL import Image

from origin_com_automation.com.origin_api import OriginController, is_origin_process_name


def origin_pids() -> set[int]:
    return {
        int(process.info["pid"])
        for process in psutil.process_iter(["pid", "name"])
        if is_origin_process_name(str(process.info.get("name", "")))
    }


def require_live_origin() -> set[int]:
    if os.getenv("ORIGIN_LIVE_SMOKE") != "1":
        pytest.skip("set ORIGIN_LIVE_SMOKE=1 to activate Origin COM")
    from origin_com_automation.com.discovery import discover_registrations

    if not any(item.available for item in discover_registrations()):
        pytest.skip("no registered Origin COM server was detected")
    before = origin_pids()
    if before and os.getenv("ORIGIN_ALLOW_EXISTING") != "1":
        pytest.skip("an Origin process is already running; live smoke will not risk attaching")
    return before


def assert_owned_exit(before: set[int]) -> None:
    for _ in range(100):
        if not (origin_pids() - before):
            break
        time.sleep(0.2)
    assert not (origin_pids() - before)
    assert before.issubset(origin_pids())


@pytest.mark.smoke
@pytest.mark.integration
def test_live_connector_matrix_image_note_and_folder_persist(tmp_path):
    before = require_live_origin()
    controller = OriginController()
    project_path = tmp_path / "objects.opju"
    matrix_ref = ""
    image_ref = ""
    note_ref = ""
    try:
        started = controller.start(progid="Origin.Application", visible=False, attach=False)
        assert started.success, started.to_dict()

        source = tmp_path / "connector.csv"
        source.write_text("x,y\n1,2\n3,4\n", encoding="ascii")
        imported = controller.import_data(
            file_path=str(source), worksheet_name="ConnectorData", has_header=True
        )
        assert imported.success, imported.to_dict()
        connector = controller.manage_connector(
            action="create",
            worksheet_ref=imported.data["worksheet_ref"],
            source=str(source),
            connector_type="csv",
        )
        assert connector.success, connector.to_dict()
        connector_ref = connector.data["worksheet_ref"]
        source.write_text("x,y\n5,6\n7,8\n", encoding="ascii")
        refreshed = controller.manage_connector(
            action="refresh", worksheet_ref=connector_ref
        )
        assert refreshed.success, refreshed.to_dict()
        read_connector = controller.read_worksheet(
            connector_ref, r1=0, c1=0, r2=4, c2=1, data_format="variant"
        )
        assert read_connector.success, read_connector.to_dict()
        assert [5.0, 6.0] in read_connector.data["values"]
        disconnected = controller.manage_connector(
            action="disconnect", worksheet_ref=connector_ref, keep_data=True
        )
        assert disconnected.success, disconnected.to_dict()

        matrix = controller.manage_matrix(action="create", matrix_ref="LiveMatrix")
        assert matrix.success, matrix.to_dict()
        matrix_ref = matrix.data["matrix_ref"]
        written = controller.manage_matrix(
            action="write", matrix_ref=matrix_ref, values=[[1, 2], [3, 4]]
        )
        assert written.success, written.to_dict()
        matrix_data = controller.manage_matrix(action="read", matrix_ref=matrix_ref)
        assert matrix_data.success, matrix_data.to_dict()
        assert [row[:2] for row in matrix_data.data["values"][:2]] == [
            [1.0, 2.0],
            [3.0, 4.0],
        ]

        image_source = tmp_path / "source.png"
        Image.new("RGB", (16, 12), "red").save(image_source)
        image = controller.manage_image(action="create", image_ref="LiveImage")
        assert image.success, image.to_dict()
        image_ref = image.data["image_ref"]
        image_import = controller.manage_image(
            action="import", image_ref=image_ref, path=str(image_source)
        )
        assert image_import.success, image_import.to_dict()
        assert image_import.data["width"] == 16
        assert image_import.data["height"] == 12

        note = controller.manage_note(
            action="create", note_ref="LiveNote", text="verified summary"
        )
        assert note.success, note.to_dict()
        note_ref = note.data["note_ref"]
        folder = controller.manage_project_folder(
            action="create", path="/Analysis/Fits"
        )
        assert folder.success, folder.to_dict()

        saved = controller.save_project_copy(target_path=str(project_path))
        assert saved.success, saved.to_dict()
    finally:
        stopped = controller.shutdown()
        assert stopped.success, stopped.to_dict()
    assert_owned_exit(before)

    reopened = OriginController()
    try:
        started = reopened.start(progid="Origin.Application", visible=False, attach=False)
        assert started.success, started.to_dict()
        opened = reopened.open_project(
            source_path=str(project_path),
            working_copy_path=str(tmp_path / "objects-reopened.opju"),
        )
        assert opened.success, opened.to_dict()
        matrix_data = reopened.manage_matrix(action="read", matrix_ref=matrix_ref)
        assert matrix_data.success, matrix_data.to_dict()
        assert [row[:2] for row in matrix_data.data["values"][:2]] == [
            [1.0, 2.0],
            [3.0, 4.0],
        ]
        image_info = reopened.manage_image(action="info", image_ref=image_ref)
        assert image_info.success, image_info.to_dict()
        assert image_info.data["width"] == 16
        note_info = reopened.manage_note(action="info", note_ref=note_ref)
        assert note_info.success, note_info.to_dict()
        assert note_info.data["text"] == "verified summary"
        folders = reopened.manage_project_folder(action="list", path="/Analysis")
        assert folders.success, folders.to_dict()
        assert "/Analysis/Fits" in folders.data["children"]
    finally:
        stopped = reopened.shutdown()
        assert stopped.success, stopped.to_dict()
    assert_owned_exit(before)
