import asyncio
import json

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from origin_com_automation.contracts import ResultEnvelope
from origin_com_automation.server import create_server


class FakeController:
    def __init__(self):
        self.calls = []

    def start(self, **kwargs):
        self.calls.append(("start", kwargs))
        return ResultEnvelope.ok({"session_id": "fake", **kwargs})

    def shutdown(self):
        self.calls.append(("shutdown", {}))
        return ResultEnvelope.ok({"shutdown": True})

    def abandon_poisoned_session(self):
        self.calls.append(("abandon_poisoned_session", {}))
        return ResultEnvelope.ok({"worker_abandoned": True})

    def run_analysis(self, **kwargs):
        self.calls.append(("run_analysis", kwargs))
        return ResultEnvelope.ok(kwargs)

    def read_worksheet(self, name, **kwargs):
        self.calls.append(("read_worksheet", {"name": name, **kwargs}))
        return ResultEnvelope.ok({"name": name, **kwargs})

    def execute_labtalk(self, **kwargs):
        self.calls.append(("execute_labtalk", kwargs))
        return ResultEnvelope.ok(kwargs)

    def configure_graph(self, **kwargs):
        self.calls.append(("configure_graph", kwargs))
        return ResultEnvelope.ok(kwargs)

    def create_plot(self, **kwargs):
        self.calls.append(("create_plot", kwargs))
        return ResultEnvelope.ok(kwargs)


def test_server_registers_the_complete_origin_tool_surface():
    server = create_server(controller=FakeController())

    tools = asyncio.run(server.list_tools())
    names = {tool.name for tool in tools}

    assert names == {
        "origin_capabilities",
        "origin_inspect_data_source",
        "origin_health_check",
        "origin_start",
        "origin_open_project",
        "origin_save_project_copy",
        "origin_save_and_replace_source",
        "origin_list_objects",
        "origin_import_data",
        "origin_read_worksheet",
        "origin_write_worksheet",
        "origin_run_analysis",
        "origin_execute_labtalk",
        "origin_create_plot",
        "origin_configure_graph",
        "origin_export_graph",
        "origin_close_project",
        "origin_recover_session",
        "origin_shutdown",
    }
    schemas = {tool.name: json.dumps(tool.inputSchema) for tool in tools}
    assert "x_tick_step" in schemas["origin_configure_graph"]
    assert "plot_styles" in schemas["origin_configure_graph"]
    assert "categorical_style" in schemas["origin_configure_graph"]
    assert "data_format" in schemas["origin_read_worksheet"]
    assert "result_string_variables" in schemas["origin_execute_labtalk"]
    assert "allow_source_overwrite" in schemas["origin_save_and_replace_source"]
    assert "initial_guess" in schemas["origin_run_analysis"]
    assert all(tool.inputSchema.get("additionalProperties") is False for tool in tools)


def test_preflight_tools_have_strict_discoverable_schemas():
    tools = asyncio.run(create_server(controller=FakeController()).list_tools())
    schemas = {tool.name: tool.inputSchema for tool in tools}

    capability = schemas["origin_capabilities"]
    assert capability["properties"]["domain"]["anyOf"][0]["enum"] == [
        "session",
        "data",
        "connector",
        "matrix",
        "image",
        "analysis",
        "graph",
        "project",
        "workflow",
    ]
    inspection = schemas["origin_inspect_data_source"]["properties"]
    assert set(inspection) == {"file_path", "sheet_name", "has_header"}


def test_capability_tool_runs_without_starting_origin():
    controller = FakeController()
    server = create_server(controller=controller)

    result = asyncio.run(server.call_tool("origin_capabilities", {"domain": "graph"}))

    assert result[1]["success"] is True
    assert "graph.scatter" in result[1]["data"]["capabilities"]
    assert controller.calls == []


def test_read_and_labtalk_schemas_expose_explicit_result_types():
    tools = asyncio.run(create_server(controller=FakeController()).list_tools())
    schemas = {tool.name: tool.inputSchema for tool in tools}

    read_format = schemas["origin_read_worksheet"]["properties"]["data_format"]
    assert read_format["default"] == "auto"
    assert read_format["enum"] == [
        "auto",
        "numeric",
        "string",
        "variant",
        "categorical_label",
    ]

    labtalk_properties = schemas["origin_execute_labtalk"]["properties"]
    assert "segments" in labtalk_properties
    assert labtalk_properties["result_numeric_variables"]["anyOf"][0] == {
        "items": {"type": "string"},
        "type": "array",
    }
    assert labtalk_properties["result_string_variables"]["anyOf"][0] == {
        "items": {"type": "string"},
        "type": "array",
    }


def test_read_and_labtalk_schemas_reject_invalid_explicit_types():
    server = create_server(controller=FakeController())

    with pytest.raises(ToolError, match="Input should be"):
        asyncio.run(
            server.call_tool(
                "origin_read_worksheet",
                {"name": "Book1", "data_format": "mixed"},
            )
        )
    with pytest.raises(ToolError, match="Input should be a valid string"):
        asyncio.run(
            server.call_tool(
                "origin_execute_labtalk",
                {"script": "x=42;", "result_numeric_variables": [42]},
            )
        )


def test_tool_top_level_rejects_unknown_arguments_instead_of_ignoring_typos():
    controller = FakeController()
    server = create_server(controller=controller)

    with pytest.raises(ToolError, match="Extra inputs are not permitted"):
        asyncio.run(
            server.call_tool(
                "origin_read_worksheet",
                {"name": "Data", "data_formatt": "string"},
            )
        )

    assert not any(call[0] == "read_worksheet" for call in controller.calls)


def test_graph_schema_strictly_describes_binding_categories_and_legend():
    tools = asyncio.run(create_server(controller=FakeController()).list_tools())
    schema = next(tool.inputSchema for tool in tools if tool.name == "origin_configure_graph")
    graph_options = schema["properties"]["options"]
    binding = graph_options["properties"]["data_binding"]["anyOf"][0]
    assert binding["additionalProperties"] is False
    assert "label_column" in binding["properties"]

    category = graph_options["properties"]["categorical_style"]["anyOf"][0]
    assert category["additionalProperties"] is False
    marker = category["properties"]["categories"]["additionalProperties"]

    assert marker["additionalProperties"] is False
    assert "required" not in marker
    assert marker["properties"]["shape"]["anyOf"][0]["enum"] == [
        "circle",
        "square",
        "triangle_up",
        "triangle_down",
        "diamond",
        "hexagon",
        "star",
        "cross",
        "x",
    ]

    legend = graph_options["properties"]["legend"]["anyOf"][1]
    assert legend["additionalProperties"] is False
    assert legend["properties"]["mode"]["const"] == "categorical"
    assert legend["properties"]["source"]["const"] == "plot_style_mapping"
    assert legend["properties"]["position"]["const"] == "top_right"
    assert "line_spacing" in legend["properties"]
    assert "show_all_categories" in legend["properties"]
    assert "auto_update" not in legend["properties"]

    create_plot = next(tool.inputSchema for tool in tools if tool.name == "origin_create_plot")
    assert "label_column" in create_plot["properties"]


def test_structured_read_labtalk_and_graph_arguments_are_forwarded():
    controller = FakeController()
    server = create_server(controller=controller)

    asyncio.run(
        server.call_tool(
            "origin_read_worksheet",
            {"name": "[WSe2Benchmark]Data", "r1": 25, "c1": 0, "r2": 25, "c2": 8},
        )
    )
    asyncio.run(
        server.call_tool(
            "origin_execute_labtalk",
            {
                "script": "codex_num=42; codex_text$=col(C)[26]$;",
                "result_numeric_variables": ["codex_num"],
                "result_string_variables": ["codex_text$"],
            },
        )
    )
    asyncio.run(
        server.call_tool(
            "origin_configure_graph",
            {
                "graph_name": "Ion_vs_Lch",
                "options": {
                    "data_binding": {
                        "worksheet_name": "[WSe2Benchmark]Data",
                        "x_column": "A",
                        "y_columns": ["B"],
                        "label_column": "C",
                        "plot_type": "scatter",
                    },
                    "categorical_style": {
                        "plot_index": 1,
                        "worksheet_name": "[WSe2Benchmark]Data",
                        "category_column": "I",
                        "categories": {
                            "this work": {
                                "color": "#2A9D55",
                                "shape": "diamond",
                                "fill": "solid",
                                "size": 14,
                            }
                        },
                    },
                    "legend": {
                        "mode": "categorical",
                        "source": "plot_style_mapping",
                        "position": "top_right",
                        "font_size": 9,
                        "line_spacing": 1.2,
                        "border": False,
                        "background": "transparent",
                        "replace_existing": True,
                        "show_all_categories": True,
                    },
                },
            },
        )
    )
    asyncio.run(
        server.call_tool(
            "origin_create_plot",
            {
                "worksheet_name": "[WSe2Benchmark]Data",
                "graph_type": "scatter",
                "x_column": "A",
                "y_columns": ["B"],
                "label_column": "C",
                "graph_name": "Ion_vs_Lch",
            },
        )
    )

    assert controller.calls[0] == (
        "read_worksheet",
        {
            "name": "[WSe2Benchmark]Data",
            "r1": 25,
            "c1": 0,
            "r2": 25,
            "c2": 8,
            "data_format": "auto",
        },
    )
    assert controller.calls[1][0] == "execute_labtalk"
    assert controller.calls[1][1]["result_numeric_variables"] == ["codex_num"]
    assert controller.calls[1][1]["result_string_variables"] == ["codex_text$"]
    assert controller.calls[2][0] == "configure_graph"
    assert controller.calls[2][1]["options"]["data_binding"]["label_column"] == "C"
    assert controller.calls[2][1]["options"]["categorical_style"]["categories"][
        "this work"
    ]["shape"] == "diamond"
    assert controller.calls[3][0] == "create_plot"
    assert controller.calls[3][1]["label_column"] == "C"


def test_graph_schema_rejects_unverified_or_unknown_categorical_options():
    server = create_server(controller=FakeController())
    base = {
        "graph_name": "Ion_vs_Lch",
        "options": {
            "categorical_style": {
                "category_column": "I",
                "categories": {"this work": {"color": "green"}},
            }
        },
    }

    with pytest.raises(ToolError, match="String should match pattern"):
        asyncio.run(server.call_tool("origin_configure_graph", base))

    with pytest.raises(ToolError, match="Extra inputs are not permitted"):
        asyncio.run(
            server.call_tool(
                "origin_configure_graph",
                {
                    "graph_name": "Ion_vs_Lch",
                    "options": {
                        "legend": {
                            "mode": "categorical",
                            "source": "plot_style_mapping",
                            "auto_update": True,
                        }
                    },
                },
            )
        )


def test_origin_start_routes_validated_arguments_to_controller():
    controller = FakeController()
    server = create_server(controller=controller)

    asyncio.run(
        server.call_tool(
            "origin_start",
            {"progid": "Origin.Application", "visible": True, "attach": False},
        )
    )

    assert controller.calls == [
        (
            "start",
            {
                "progid": "Origin.Application",
                "visible": True,
                "attach": False,
                "exclusive": False,
            },
        )
    ]


def test_recovery_replaces_the_controller_before_the_next_start():
    previous = FakeController()
    replacement = FakeController()
    server = create_server(
        controller=previous,
        controller_factory=lambda: replacement,
    )

    recovered = asyncio.run(server.call_tool("origin_recover_session", {}))
    asyncio.run(server.call_tool("origin_start", {"visible": False}))

    assert recovered[1]["success"] is True
    assert previous.calls == [("abandon_poisoned_session", {})]
    assert replacement.calls == [
        (
            "start",
            {
                "progid": None,
                "visible": False,
                "attach": None,
                "exclusive": False,
            },
        )
    ]


def test_analysis_schema_rejects_unknown_options_and_preserves_selection():
    controller = FakeController()
    server = create_server(controller=controller)

    with pytest.raises(ToolError, match="Extra inputs are not permitted"):
        asyncio.run(
            server.call_tool(
                "origin_run_analysis",
                {
                    "worksheet_name": "Book1",
                    "method": "linear_fit",
                    "x_column": "A",
                    "y_column": "B",
                    "options": {"branch": "reverse"},
                },
            )
        )
    asyncio.run(
        server.call_tool(
            "origin_run_analysis",
            {
                "worksheet_name": "Book1",
                "method": "derivative",
                "x_column": "A",
                "y_column": "B",
                "row_start": 10,
                "row_end": 20,
                "row_order": "reverse",
                "filters": [{"column": "y", "operator": "gt", "value": 0}],
                "options": {"derivative_method": "central", "order": 1},
            },
        )
    )

    call = next(item for item in controller.calls if item[0] == "run_analysis")
    assert call[1]["row_start"] == 10
    assert call[1]["row_order"] == "reverse"
    assert call[1]["options"] == {"order": 1, "derivative_method": "central"}
