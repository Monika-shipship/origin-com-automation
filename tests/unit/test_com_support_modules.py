from pathlib import Path

from origin_com_automation.com import graph_support, project_support, worksheet_support
from origin_com_automation.com import origin_api


class Collection:
    def __init__(self, items):
        self._items = list(items)
        self.Count = len(self._items)

    def Item(self, index):
        return self._items[index]


def test_origin_api_reexports_extracted_support_helpers():
    assert origin_api._column_profile is worksheet_support.column_profile
    assert origin_api._graph_page_name is graph_support.graph_page_name
    assert origin_api._project_path_parts is project_support.project_path_parts


def test_worksheet_support_preserves_mixed_values_and_header_detection():
    values = [0.041, "NA", "≈1", None]
    assert worksheet_support.column_profile(values) == {
        "non_empty_count": 3,
        "numeric_count": 1,
        "text_count": 2,
        "missing_count": 1,
    }
    assert worksheet_support.column_data_format(values) == 9
    assert worksheet_support.split_header(
        [["Vg", "Ion"], [0, 2260], [1, 950]],
        None,
    ) == (["Vg", "Ion"], [[0, 2260], [1, 950]])


def test_graph_support_preserves_normalization_and_command_generation():
    assert graph_support.normalize_graph_data_binding(
        {
            "worksheet_name": "[Book1]Data",
            "x_column": "A",
            "y_columns": ["B"],
            "plot_type": "scatter",
        }
    ) == {
        "worksheet_name": "[Book1]Data",
        "x_column": "A",
        "y_columns": ["B"],
        "plot_type": "scatter",
    }
    assert graph_support.graph_configuration_commands(
        {"x_scale": "log10", "legend": False},
        None,
    ) == ["layer.x.type=2;", "legend -d;"]


def test_project_support_preserves_paths_and_collection_access(tmp_path: Path):
    item = object()
    assert project_support.collection_items(Collection([item])) == [item]
    assert project_support.project_path_parts(r"Root\Analysis/Results") == [
        "Root",
        "Analysis",
        "Results",
    ]
    target = tmp_path / "project.opju"
    target.write_bytes(b"origin")
    assert project_support.file_identity(target) is not None

