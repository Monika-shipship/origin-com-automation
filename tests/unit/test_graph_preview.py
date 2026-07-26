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
