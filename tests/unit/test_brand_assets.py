from pathlib import Path
from xml.etree import ElementTree

import pytest
from PIL import Image, ImageStat


ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"


@pytest.mark.parametrize(
    ("filename", "expected_size"),
    [
        ("origin-automation-logo.png", (512, 512)),
        ("origin-automation-composer.png", (128, 128)),
    ],
)
def test_brand_png_is_the_expected_size_and_nonblank(
    filename: str, expected_size: tuple[int, int]
):
    path = ASSETS / filename

    assert path.is_file(), f"missing brand asset: {path.relative_to(ROOT)}"
    with Image.open(path) as image:
        assert image.format == "PNG"
        assert image.size == expected_size
        rgb = image.convert("RGB")
        channel_extrema = rgb.getextrema()
        channel_variance = ImageStat.Stat(rgb).var

    assert all(low < high for low, high in channel_extrema)
    assert all(variance > 100 for variance in channel_variance)


def test_svg_master_uses_the_brand_palette_without_originlab_artwork():
    path = ASSETS / "origin-automation-logo.svg"

    assert path.is_file(), f"missing brand asset: {path.relative_to(ROOT)}"
    svg = path.read_text(encoding="utf-8")
    root = ElementTree.fromstring(svg)
    normalized_svg = svg.casefold()

    assert root.attrib.get("viewBox") == "0 0 512 512"
    assert "#df5b3f" in normalized_svg
    assert "#278f7a" in normalized_svg
    assert "originlab" not in normalized_svg
