"""Render the Plot Workspace brand assets from normalized geometry."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

CANVAS = 512
SUPERSAMPLE = 4
WHITE = "#FFFFFF"
PANEL = "#EEF1F3"
CHARCOAL = "#252B33"
CORAL = "#DF5B3F"
TEAL = "#278F7A"

TILE = (16, 16, 496, 496)
WORKSPACE = (72, 72, 440, 440)
Y_AXIS = ((144, 346), (144, 158))
X_AXIS = ((144, 346), (378, 346))
CURVE = (
    (164, 316),
    (190, 308),
    (203, 274),
    (228, 258),
    (255, 241),
    (277, 220),
    (307, 207),
    (330, 197),
    (348, 184),
    (370, 174),
)
POINTS = ((228, 258), (307, 207))


def _svg() -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect x="16" y="16" width="480" height="480" rx="108" fill="{WHITE}"/>
  <rect x="72" y="72" width="368" height="368" rx="38" fill="{PANEL}"/>
  <path d="M144 158 V346 H378" fill="none" stroke="{CHARCOAL}" stroke-width="18" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M164 316 C190 308 203 274 228 258 C255 241 277 220 307 207 C330 197 348 184 370 174" fill="none" stroke="{CORAL}" stroke-width="18" stroke-linecap="round"/>
  <circle cx="228" cy="258" r="22" fill="{TEAL}" stroke="{WHITE}" stroke-width="8"/>
  <circle cx="307" cy="207" r="22" fill="{TEAL}" stroke="{WHITE}" stroke-width="8"/>
</svg>
"""


def _scale_point(point: tuple[int, int], scale: float) -> tuple[int, int]:
    return round(point[0] * scale), round(point[1] * scale)


def _scale_box(box: tuple[int, int, int, int], scale: float) -> tuple[int, ...]:
    return tuple(round(value * scale) for value in box)


def _rounded_line(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[int, int]],
    *,
    fill: str,
    width: int,
) -> None:
    radius = width // 2
    draw.line(points, fill=fill, width=width, joint="curve")
    for x, y in (points[0], points[-1]):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)


def _curve_points(scale: float) -> list[tuple[int, int]]:
    segments = (CURVE[:4], CURVE[3:7], CURVE[6:])
    sampled: list[tuple[int, int]] = []
    for segment in segments:
        p0, p1, p2, p3 = segment
        for step in range(33):
            t = step / 32
            u = 1 - t
            x = u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0]
            y = u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1]
            point = round(x * scale), round(y * scale)
            if not sampled or point != sampled[-1]:
                sampled.append(point)
    return sampled


def _render_png(size: int) -> Image.Image:
    scale = size * SUPERSAMPLE / CANVAS
    rendered_size = size * SUPERSAMPLE
    image = Image.new("RGBA", (rendered_size, rendered_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        _scale_box(TILE, scale), radius=round(108 * scale), fill=WHITE
    )
    draw.rounded_rectangle(
        _scale_box(WORKSPACE, scale), radius=round(38 * scale), fill=PANEL
    )
    axis_width = round(18 * scale)
    _rounded_line(
        draw,
        [_scale_point(point, scale) for point in Y_AXIS],
        fill=CHARCOAL,
        width=axis_width,
    )
    _rounded_line(
        draw,
        [_scale_point(point, scale) for point in X_AXIS],
        fill=CHARCOAL,
        width=axis_width,
    )
    _rounded_line(draw, _curve_points(scale), fill=CORAL, width=round(18 * scale))

    point_radius = round(22 * scale)
    point_outline = round(8 * scale)
    for point in POINTS:
        x, y = _scale_point(point, scale)
        draw.ellipse(
            (x - point_radius, y - point_radius, x + point_radius, y + point_radius),
            fill=TEAL,
            outline=WHITE,
            width=point_outline,
        )

    return image.resize((size, size), Image.Resampling.LANCZOS)


def _write_qa_sheet(root: Path, logo: Image.Image, composer: Image.Image) -> None:
    qa = Image.new("RGB", (1408, 768), "#E4E7EA")
    ImageDraw.Draw(qa).rectangle((704, 0, 1408, 768), fill="#20252B")
    for x, image in ((96, logo), (800, logo), (288, composer), (992, composer)):
        y = 48 if image.width == 512 else 608
        qa.paste(image, (x, y), image)
    path = root / "artifacts" / "brand" / "icon-qa.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    qa.save(path, format="PNG", optimize=False)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    assets = root / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "origin-automation-logo.svg").write_text(_svg(), encoding="utf-8")

    logo = _render_png(512)
    composer = _render_png(128)
    logo.save(assets / "origin-automation-logo.png", format="PNG", optimize=False)
    composer.save(assets / "origin-automation-composer.png", format="PNG", optimize=False)
    _write_qa_sheet(root, logo, composer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
