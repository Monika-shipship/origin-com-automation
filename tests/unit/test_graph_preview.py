from PIL import Image, ImageDraw

from origin_com_automation.graphs.preview import inspect_png


def test_png_metrics_detect_blank_and_nonblank_content(tmp_path):
    blank = tmp_path / "blank.png"
    Image.new("RGBA", (20, 10), "white").save(blank)
    blank_metrics = inspect_png(blank)
    assert blank_metrics["nonblank_ratio"] == 0

    plotted = tmp_path / "plot.png"
    image = Image.new("RGBA", (20, 10), "white")
    ImageDraw.Draw(image).rectangle((5, 2, 14, 7), fill="#ff0000")
    image.save(plotted)
    metrics = inspect_png(plotted, expected_colors=["#ff0000", "#0000ff"], tolerance=0)
    assert metrics["dimensions"] == [20, 10]
    assert metrics["nonblank_ratio"] == 0.3
    assert metrics["expected_color_pixels"]["#ff0000"] == 60
    assert metrics["expected_color_pixels"]["#0000ff"] == 0
    assert metrics["content_bbox"] == [5, 2, 14, 7]


def test_transparent_png_reports_alpha_coverage(tmp_path):
    path = tmp_path / "transparent.png"
    image = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((0, 0, 4, 9), fill=(0, 255, 0, 255))
    image.save(path)
    metrics = inspect_png(path)
    assert metrics["alpha_coverage"] == 0.5


def test_png_qa_detects_edge_contact_whitespace_and_clipping(tmp_path):
    edge = tmp_path / "edge.png"
    image = Image.new("RGBA", (100, 100), "white")
    ImageDraw.Draw(image).rectangle((0, 45, 99, 54), fill="black")
    image.save(edge)
    metrics = inspect_png(edge, edge_margin=2, maximum_whitespace_ratio=0.85)
    assert metrics["content_touches_edge"] is True
    assert metrics["whitespace_ratio"] == 0.9
    assert metrics["suspected_clipping"] is True
    assert metrics["qa_passed"] is False


def test_sparse_scientific_plot_uses_bbox_coverage_not_ink_density(tmp_path):
    path = tmp_path / "sparse-plot.png"
    image = Image.new("RGBA", (100, 100), "white")
    ImageDraw.Draw(image).rectangle((10, 10, 90, 90), outline="black", width=1)
    image.save(path)
    metrics = inspect_png(path)
    assert metrics["nonblank_ratio"] < 0.05
    assert metrics["content_bbox_coverage"] > 0.6
    assert metrics["suspected_clipping"] is False
    assert metrics["qa_passed"] is True
