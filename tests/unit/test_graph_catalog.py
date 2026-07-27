import pytest

from origin_com_automation.graphs.catalog import GraphCatalogError, graph_catalog, validate_graph_request
from origin_com_automation.graphs.palettes import palette_catalog


def test_catalog_covers_requested_graph_families_and_roles():
    catalog = graph_catalog()
    for graph_id in [
        "scatter", "line", "bar", "histogram", "box", "violin",
        "polar", "ternary", "contour", "heatmap", "surface_3d", "scatter_3d",
    ]:
        assert graph_id in catalog
        assert catalog[graph_id]["required_roles"]
        assert catalog[graph_id]["status"] in {"verified", "supported_unverified"}
    assert catalog["ternary"]["required_roles"] == ["a", "b", "c"]
    assert catalog["surface_3d"]["input_kind"] == "matrix"


def test_graph_request_rejects_missing_or_extra_roles():
    with pytest.raises(GraphCatalogError, match="missing roles"):
        validate_graph_request("ternary", {"a": "A", "b": "B"})
    with pytest.raises(GraphCatalogError, match="unsupported roles"):
        validate_graph_request("scatter", {"x": "A", "y": "B", "z": "C"})


def test_typed_graph_routes_are_registered_once_in_the_catalog():
    catalog = graph_catalog()
    assert {"semilog", "loglog", "multi_layer"} <= set(catalog)
    assert catalog["semilog"]["plot_id"] == catalog["line"]["plot_id"]
    assert catalog["multi_layer"]["plot_id"] == catalog["line_symbol"]["plot_id"]


def test_palette_catalog_has_stable_ids_and_exact_hex_colors():
    palettes = palette_catalog()
    assert "scientific_default" in palettes
    assert palettes["colorblind_safe"]["colors"][0].startswith("#")
    assert all(len(color) == 7 for item in palettes.values() for color in item["colors"])
