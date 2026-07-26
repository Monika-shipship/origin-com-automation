from pathlib import Path

import pytest

from origin_com_automation.objects.connectors import build_connector_plan
from origin_com_automation.objects.images import build_image_plan
from origin_com_automation.objects.matrices import build_matrix_plan
from origin_com_automation.objects.validation import ObjectPlanError


def test_connector_create_normalizes_source_and_requires_supported_type(tmp_path):
    source = tmp_path / "data file.csv"
    source.write_text("x,y\n1,2\n", encoding="utf-8")
    plan = build_connector_plan(
        action="create",
        worksheet_ref="[Book1]Data",
        source=str(source),
        connector_type="csv",
        keep_connector=True,
    )
    assert plan.source == source.resolve()
    assert plan.verification == "connector_state_and_source"

    with pytest.raises(ObjectPlanError, match="connector_type"):
        build_connector_plan(
            action="create",
            worksheet_ref="[Book1]Data",
            source=str(source),
            connector_type="json",
        )


def test_connector_disconnect_requires_explicit_keep_data_policy():
    with pytest.raises(ObjectPlanError, match="keep_data"):
        build_connector_plan(action="disconnect", worksheet_ref="[Book1]Data")
    plan = build_connector_plan(
        action="disconnect", worksheet_ref="[Book1]Data", keep_data=True
    )
    assert plan.keep_data is True


def test_matrix_write_requires_rectangular_finite_block():
    plan = build_matrix_plan(
        action="write",
        matrix_ref="[MBook1]MSheet1",
        values=[[1, 2], [3, 4]],
        row=2,
        column=3,
    )
    assert plan.shape == (2, 2)
    assert plan.expected_range == (2, 3, 3, 4)
    with pytest.raises(ObjectPlanError, match="rectangular"):
        build_matrix_plan(
            action="write", matrix_ref="[MBook1]MSheet1", values=[[1], [2, 3]]
        )


def test_matrix_transform_has_closed_operation_set():
    plan = build_matrix_plan(
        action="transform",
        matrix_ref="[MBook1]MSheet1",
        operation="transpose",
    )
    assert plan.command == "matrix -t;"
    with pytest.raises(ObjectPlanError, match="operation"):
        build_matrix_plan(
            action="transform",
            matrix_ref="[MBook1]MSheet1",
            operation="arbitrary_script",
        )


def test_image_import_and_export_validate_paths_and_extensions(tmp_path):
    image = tmp_path / "source.png"
    image.write_bytes(b"not-a-real-png")
    imported = build_image_plan(action="import", image_ref="Image1", path=str(image))
    assert imported.path == image.resolve()

    exported = build_image_plan(
        action="export",
        image_ref="Image1",
        path=str(tmp_path / "out.tiff"),
        overwrite=False,
    )
    assert exported.path.suffix == ".tiff"
    with pytest.raises(ObjectPlanError, match="extension"):
        build_image_plan(
            action="export", image_ref="Image1", path=str(tmp_path / "bad.svg")
        )


def test_image_payload_limit_is_fail_closed(tmp_path):
    image = tmp_path / "large.png"
    image.write_bytes(b"x" * 1025)
    with pytest.raises(ObjectPlanError, match="payload limit"):
        build_image_plan(
            action="import",
            image_ref="Image1",
            path=str(image),
            max_bytes=1024,
        )
