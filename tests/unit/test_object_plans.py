import pytest

from origin_com_automation.objects.connectors import (
    build_connector_plan,
    connector_header_state,
    connector_options_with_header,
    connector_type_for_source,
)
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
    assert plan.selection is None
    assert plan.has_header is None
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


def test_connector_create_preserves_selection_and_explicit_header_policy(tmp_path):
    source = tmp_path / "data.xlsx"
    source.write_bytes(b"fixture")

    plan = build_connector_plan(
        action="create",
        worksheet_ref="[Book1]Data",
        source=str(source),
        connector_type="excel",
        selection="Target Sheet",
        has_header=True,
    )

    assert plan.selection == "Target Sheet"
    assert plan.has_header is True
    with pytest.raises(ObjectPlanError, match="only accepted for connector create"):
        build_connector_plan(
            action="refresh",
            worksheet_ref="[Book1]Data",
            has_header=True,
        )


def test_connector_options_apply_explicit_csv_and_excel_header_policy():
    csv_options = (
        '<OriginStorage><CSV/><Settings><heading>0</heading></Settings></OriginStorage>'
    )
    excel_options = (
        '<OriginStorage><Excel/><Settings><mainheader>-1</mainheader>'
        '<labels Use="0"><longname>0</longname>'
        '</labels></Settings></OriginStorage>'
    )

    assert "<heading>1</heading>" in connector_options_with_header(
        csv_options, connector_type="csv", has_header=True
    )
    without_header = connector_options_with_header(
        excel_options, connector_type="excel", has_header=False
    )
    assert "<mainheader>0</mainheader>" in without_header
    assert '<labels Use="0">' in without_header
    assert "<longname>0</longname>" in without_header
    assert connector_header_state(without_header, connector_type="excel") is False

    with_header = connector_options_with_header(
        excel_options, connector_type="excel", has_header=True
    )
    assert "<mainheader>0</mainheader>" in with_header
    assert '<labels Use="1">' in with_header
    assert "<longname>1</longname>" in with_header
    assert connector_header_state(with_header, connector_type="excel") is True


def test_connector_type_is_derived_from_supported_local_source_extensions(tmp_path):
    assert connector_type_for_source(tmp_path / "data.csv") == "csv"
    assert connector_type_for_source(tmp_path / "data.tsv") == "csv"
    assert connector_type_for_source(tmp_path / "data.xlsx") == "excel"
    assert connector_type_for_source(tmp_path / "data.xlsm") == "excel"
    with pytest.raises(ObjectPlanError, match="connector-supported"):
        connector_type_for_source(tmp_path / "data.json")


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


def test_matrix_and_image_create_plans_are_explicit():
    matrix = build_matrix_plan(action="create", matrix_ref="LiveMatrix")
    image = build_image_plan(action="create", image_ref="LiveImage")
    assert matrix.action == "create"
    assert image.action == "create"
    assert image.path is None


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
