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

    def import_data(self, **kwargs):
        self.calls.append(("import_data", kwargs))
        return ResultEnvelope.ok(kwargs)

    def execute_labtalk(self, **kwargs):
        self.calls.append(("execute_labtalk", kwargs))
        return ResultEnvelope.ok(kwargs)

    def configure_graph(self, **kwargs):
        self.calls.append(("configure_graph", kwargs))
        return ResultEnvelope.ok(kwargs)

    def create_plot(self, **kwargs):
        self.calls.append(("create_plot", kwargs))
        return ResultEnvelope.ok(kwargs)

    def run_xfunction(self, **kwargs):
        self.calls.append(("run_xfunction", kwargs))
        return ResultEnvelope.ok(kwargs)

    def list_analysis_operations(self, **kwargs):
        self.calls.append(("list_analysis_operations", kwargs))
        return ResultEnvelope.ok(kwargs)

    def get_analysis_operation(self, **kwargs):
        self.calls.append(("get_analysis_operation", kwargs))
        return ResultEnvelope.ok(kwargs)

    def recalculate_analysis(self, **kwargs):
        self.calls.append(("recalculate_analysis", kwargs))
        return ResultEnvelope.ok(kwargs)

    def manage_analysis_template(self, **kwargs):
        self.calls.append(("manage_analysis_template", kwargs))
        return ResultEnvelope.ok(kwargs)

    def transform_worksheet(self, **kwargs):
        self.calls.append(("transform_worksheet", kwargs))
        return ResultEnvelope.ok(kwargs)

    def set_column_formula(self, **kwargs):
        self.calls.append(("set_column_formula", kwargs))
        return ResultEnvelope.ok(kwargs)

    def manage_connector(self, **kwargs):
        self.calls.append(("manage_connector", kwargs))
        return ResultEnvelope.ok(kwargs)

    def manage_matrix(self, **kwargs):
        self.calls.append(("manage_matrix", kwargs))
        return ResultEnvelope.ok(kwargs)

    def manage_image(self, **kwargs):
        self.calls.append(("manage_image", kwargs))
        return ResultEnvelope.ok(kwargs)

    def create_graph(self, **kwargs):
        self.calls.append(("create_graph", kwargs))
        return ResultEnvelope.ok(kwargs)

    def manage_graph_layout(self, **kwargs):
        self.calls.append(("manage_graph_layout", kwargs))
        return ResultEnvelope.ok(kwargs)

    def apply_graph_template(self, **kwargs):
        self.calls.append(("apply_graph_template", kwargs))
        return ResultEnvelope.ok(kwargs)

    def view_graph(self, **kwargs):
        self.calls.append(("view_graph", kwargs))
        return ResultEnvelope.ok(kwargs)

    def manage_project_folder(self, **kwargs):
        self.calls.append(("manage_project_folder", kwargs))
        return ResultEnvelope.ok(kwargs)

    def manage_note(self, **kwargs):
        self.calls.append(("manage_note", kwargs))
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
        "origin_run_xfunction",
        "origin_list_analysis_operations",
        "origin_get_analysis_operation",
        "origin_recalculate_analysis",
        "origin_manage_analysis_template",
        "origin_transform_worksheet",
        "origin_set_column_formula",
        "origin_manage_connector",
        "origin_manage_matrix",
        "origin_manage_image",
        "origin_graph_catalog",
        "origin_palette_catalog",
        "origin_create_graph",
        "origin_manage_graph_layout",
        "origin_list_graph_templates",
        "origin_apply_graph_template",
        "origin_inspect_png",
        "origin_view_graph",
        "origin_plan_figure",
        "origin_execute_figure",
        "origin_submit_batch",
        "origin_task_status",
        "origin_cancel_task",
        "origin_manage_project_folder",
        "origin_manage_note",
        "origin_query_knowledge",
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
    assert "before_script" in schemas["origin_set_column_formula"]
    assert "row_start" in schemas["origin_set_column_formula"]
    assert "row_end" in schemas["origin_set_column_formula"]
    assert "recalculate_mode" in schemas["origin_set_column_formula"]
    assert "selection" in schemas["origin_manage_connector"]
    assert "has_header" in schemas["origin_manage_connector"]
    analysis_schema = json.loads(schemas["origin_run_analysis"])["properties"]["options"]["anyOf"][0]
    assert analysis_schema["additionalProperties"] is False
    for option_name in [
        "backend",
        "interpolation_kind",
        "interpolation_points",
        "normalization_method",
        "sample_spacing",
        "correlation_method",
        "alternative",
        "groups",
        "components",
        "bounds",
        "parameter_names",
        "create_operation",
        "recalculate_mode",
    ]:
        assert option_name in analysis_schema["properties"]
    assert all(tool.inputSchema.get("additionalProperties") is False for tool in tools)


def test_source_and_analysis_schemas_default_to_editable_origin_workflows():
    tools = asyncio.run(create_server(controller=FakeController()).list_tools())
    schemas = {tool.name: tool.inputSchema for tool in tools}

    import_properties = schemas["origin_import_data"]["properties"]
    assert import_properties["source_mode"]["default"] == "linked"
    assert set(import_properties["source_mode"]["enum"]) == {"linked", "snapshot"}

    options = schemas["origin_run_analysis"]["properties"]["options"]["anyOf"][0]
    properties = options["properties"]
    assert properties["backend"]["default"] == "origin_native"
    assert properties["create_operation"]["default"] is True
    assert properties["recalculate_mode"]["default"] == "auto"

    transform_options = schemas["origin_transform_worksheet"]["properties"]["options"]["anyOf"][0]
    transform_properties = transform_options["properties"]
    assert transform_properties["execution_mode"]["default"] == "origin_native"
    assert set(transform_properties["execution_mode"]["enum"]) == {
        "origin_native",
        "materialized",
    }
    assert transform_properties["recalculate_mode"]["default"] == "auto"


def test_import_tool_forwards_linked_source_mode_by_default():
    controller = FakeController()
    server = create_server(controller=controller)

    result = asyncio.run(
        server.call_tool("origin_import_data", {"file_path": "C:\\data\\input.csv"})
    )

    assert result[1]["success"] is True
    assert controller.calls == [
        (
            "import_data",
            {
                "file_path": "C:\\data\\input.csv",
                "worksheet_name": None,
                "sheet_name": None,
                "has_header": None,
                "target_mode": "new_workbook",
                "source_mode": "linked",
            },
        )
    ]


def test_formula_tool_forwards_origin_native_formula_contract():
    controller = FakeController()
    server = create_server(controller=controller)

    result = asyncio.run(
        server.call_tool(
            "origin_set_column_formula",
            {
                "worksheet_ref": "[Book1]Data",
                "column": "C",
                "formula": "col(A)*col(B)",
                "before_script": "double scale=1;",
                "row_start": 0,
                "row_end": 25,
            },
        )
    )

    assert result[1]["success"] is True
    assert controller.calls == [
        (
            "set_column_formula",
            {
                "worksheet_ref": "[Book1]Data",
                "column": "C",
                "formula": "col(A)*col(B)",
                "before_script": "double scale=1;",
                "row_start": 0,
                "row_end": 25,
                "recalculate_mode": "auto",
            },
        )
    ]


def test_calculated_column_transform_forwards_native_defaults():
    controller = FakeController()
    server = create_server(controller=controller)

    result = asyncio.run(
        server.call_tool(
            "origin_transform_worksheet",
            {
                "source_ref": "[Book1]Data",
                "destination_ref": "[Book1]Data",
                "action": "calculated_column",
                "options": {
                    "name": "product",
                    "left": "A",
                    "operator": "multiply",
                    "right": "B",
                },
            },
        )
    )

    assert result[1]["success"] is True
    assert controller.calls == [
        (
            "transform_worksheet",
            {
                "source_ref": "[Book1]Data",
                "destination_ref": "[Book1]Data",
                "action": "calculated_column",
                "options": {
                    "operator": "multiply",
                    "name": "product",
                    "left": "A",
                    "right": "B",
                    "execution_mode": "origin_native",
                    "before_script": "",
                    "row_start": 0,
                    "row_end": -1,
                    "recalculate_mode": "auto",
                },
            },
        )
    ]


def test_graph_expansion_tools_have_explicit_roles_and_safety_gates():
    tools = asyncio.run(create_server(controller=FakeController()).list_tools())
    schemas = {tool.name: tool.inputSchema for tool in tools}
    create = schemas["origin_create_graph"]["properties"]
    assert set(create) == {"graph_type", "roles", "graph_name", "allow_unverified"}
    assert create["allow_unverified"]["default"] is False
    template = schemas["origin_apply_graph_template"]["properties"]
    assert "expected_sha256" in template
    assert "required_layers" in template
    preview = schemas["origin_view_graph"]["properties"]
    assert "expected_colors" in preview
    assert "tolerance" in preview


def test_graph_catalog_and_palette_tools_do_not_start_origin():
    controller = FakeController()
    server = create_server(controller=controller)
    catalog = asyncio.run(server.call_tool("origin_graph_catalog", {}))
    palettes = asyncio.run(server.call_tool("origin_palette_catalog", {}))
    assert catalog[1]["success"] is True
    assert "ternary" in catalog[1]["data"]["graph_types"]
    assert palettes[1]["success"] is True
    assert controller.calls == []


def test_view_graph_returns_text_envelope_and_image_content(tmp_path):
    from PIL import Image

    preview = tmp_path / "preview.png"
    Image.new("RGB", (12, 8), "white").save(preview)

    class PreviewController(FakeController):
        def view_graph(self, **kwargs):
            return ResultEnvelope.ok(
                {"preview_path": str(preview), "pixel_metrics": {"dimensions": [12, 8]}}
            )

    result = asyncio.run(
        create_server(controller=PreviewController()).call_tool(
            "origin_view_graph", {"graph_name": "Graph1"}
        )
    )
    content = result[0]
    assert any(item.type == "text" and '"success": true' in item.text for item in content)
    image = next(item for item in content if item.type == "image")
    assert image.mimeType == "image/png"
    assert image.data


def test_figurespec_schema_and_plan_tool_are_strict_and_digest_bound(tmp_path):
    source = tmp_path / "input.csv"
    source.write_text("x,y\n1,2\n", encoding="utf-8")
    spec = {
        "route": "data_to_project",
        "input": {"path": str(source), "worksheet_ref": "[Book1]Data"},
        "plots": [],
        "outputs": {"project_path": str(tmp_path / "out.opju")},
    }
    server = create_server(controller=FakeController())
    result = asyncio.run(server.call_tool("origin_plan_figure", {"spec": spec}))
    assert result[1]["success"] is True
    assert result[1]["data"]["executor_executable"] is True
    assert len(result[1]["data"]["digest"]) == 64

    schemas = {tool.name: tool.inputSchema for tool in asyncio.run(server.list_tools())}
    figure = schemas["origin_plan_figure"]["properties"]["spec"]
    assert figure["additionalProperties"] is False
    assert "route" in figure["properties"]
    assert "plan_digest" in schemas["origin_execute_figure"]["properties"]


def test_native_tool_schemas_expose_discriminated_parameter_types():
    tools = asyncio.run(create_server(controller=FakeController()).list_tools())
    schemas = {tool.name: tool.inputSchema for tool in tools}
    run_schema = schemas["origin_run_xfunction"]

    parameter_schema = run_schema["properties"]["parameters"]["additionalProperties"]
    serialized = json.dumps(parameter_schema)
    for native_type in ["range", "file", "string", "number", "integer", "boolean"]:
        assert f'"const": "{native_type}"' in serialized
    assert run_schema["properties"]["recalculate_mode"]["enum"] == [
        "none",
        "auto",
        "manual",
    ]
    assert run_schema["properties"]["outputs"]["anyOf"][0][
        "additionalProperties"
    ]["additionalProperties"] is False


def test_native_tool_decodes_structured_values_before_forwarding():
    controller = FakeController()
    server = create_server(controller=controller)

    result = asyncio.run(
        server.call_tool(
            "origin_run_xfunction",
            {
                "name": "fitlr",
                "parameters": {"ix": {"type": "range", "value": "[Book1]Data!A:B"}},
                "outputs": {"oy": {"type": "output", "value": "[Book1]Fit!A:B"}},
                "create_operation": True,
                "recalculate_mode": "auto",
            },
        )
    )

    assert result[1]["success"] is True
    call = next(item for item in controller.calls if item[0] == "run_xfunction")
    assert call[1]["parameters"]["ix"].value == "[Book1]Data!A:B"
    assert call[1]["outputs"]["oy"].value == "[Book1]Fit!A:B"


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
    assert call[1]["options"] == {
        "backend": "origin_native",
        "order": 1,
        "derivative_method": "central",
        "create_operation": True,
        "recalculate_mode": "auto",
    }
