from pathlib import Path

import pytest

from origin_com_automation.services.analysis import build_analysis_request
from origin_com_automation.services.exports import select_changed_artifact, snapshot_artifacts
from origin_com_automation.services.projects import (
    SourceOverwriteError,
    copy_project,
    validate_artifact,
)
from origin_com_automation.services.worksheets import find_object, table_from_com_value


def test_copy_project_creates_a_distinct_working_file(tmp_path):
    source = tmp_path / "source.opju"
    source.write_bytes(b"origin-project")
    target = tmp_path / "working.opju"

    copied = copy_project(source, target)

    assert copied == target.resolve()
    assert copied.read_bytes() == source.read_bytes()
    assert copied != source.resolve()
    assert validate_artifact(copied) is True


def test_copy_project_rejects_overwriting_source(tmp_path):
    source = tmp_path / "source.opju"
    source.write_bytes(b"origin-project")

    with pytest.raises(SourceOverwriteError):
        copy_project(source, source)


def test_object_lookup_uses_identifier_or_unique_name():
    objects = [
        {"id": "book-1", "name": "IVG", "type": "workbook"},
        {"id": "graph-1", "name": "Transfer", "type": "graph"},
    ]

    assert find_object(objects, identifier="graph-1")["type"] == "graph"
    assert find_object(objects, name="IVG")["id"] == "book-1"


def test_table_from_com_value_normalizes_scalars_and_empty_cells():
    assert table_from_com_value(((1, 2), (3, None))) == [[1, 2], [3, None]]
    assert table_from_com_value(7) == [[7]]
    assert table_from_com_value(None) == []


def test_analysis_request_requires_explicit_columns_and_method():
    request = build_analysis_request(
        method="linear_fit",
        x_column="Vg",
        y_column="Id",
    )

    assert request.method == "linear_fit"
    assert request.x_column == "Vg"
    assert request.options == {}

    with pytest.raises(ValueError, match="Unsupported linear_fit options"):
        build_analysis_request(
            method="linear_fit",
            x_column="Vg",
            y_column="Id",
            options={"branch": "reverse"},
        )

    with pytest.raises(ValueError):
        build_analysis_request(method="unknown", x_column="Vg", y_column="Id")


def test_rename_export_selects_new_file_instead_of_existing_target(tmp_path):
    old = tmp_path / "graph.png"
    old.write_bytes(b"old")
    before = snapshot_artifacts(tmp_path, "graph")
    renamed = tmp_path / "graph1.png"
    renamed.write_bytes(b"new-image")

    selected = select_changed_artifact(
        tmp_path,
        "graph",
        before,
        suffixes={".png"},
    )

    assert selected == renamed.resolve()
