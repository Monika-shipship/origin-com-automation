"""Render the Plot Workspace brand assets from normalized geometry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

Point = tuple[int, int]
Box = tuple[int, int, int, int]

SUPERSAMPLE = 4
PNG_COMPRESSION_LEVEL = 9
WHITE = "#FFFFFF"
PANEL = "#EEF1F3"
CHARCOAL = "#252B33"
CORAL = "#DF5B3F"
TEAL = "#278F7A"


@dataclass(frozen=True)
class RoundedRect:
    box: Box
    radius: int
    fill: str


@dataclass(frozen=True)
class Polyline:
    points: tuple[Point, ...]
    stroke: str
    width: int


@dataclass(frozen=True)
class BezierPath:
    start: Point
    segments: tuple[tuple[Point, Point, Point], ...]
    stroke: str
    width: int


@dataclass(frozen=True)
class Circle:
    center: Point
    outer_radius: int
    fill: str
    outline: str
    outline_width: int


@dataclass(frozen=True)
class BrandGeometry:
    canvas: int
    tile: RoundedRect
    workspace: RoundedRect
    axis: Polyline
    curve: BezierPath
    points: tuple[Circle, ...]


BRAND = BrandGeometry(
    canvas=512,
    tile=RoundedRect((16, 16, 496, 496), 108, WHITE),
    workspace=RoundedRect((72, 72, 440, 440), 38, PANEL),
    axis=Polyline(((144, 158), (144, 346), (378, 346)), CHARCOAL, 18),
    curve=BezierPath(
        start=(164, 316),
        segments=(
            ((190, 308), (203, 274), (228, 258)),
            ((255, 241), (277, 220), (307, 207)),
            ((330, 197), (348, 184), (370, 174)),
        ),
        stroke=CORAL,
        width=18,
    ),
    points=(
        Circle((228, 258), 22, TEAL, WHITE, 8),
        Circle((307, 207), 22, TEAL, WHITE, 8),
    ),
)


def _svg_rect(rect: RoundedRect) -> str:
    left, top, right, bottom = rect.box
    return (
        f'<rect x="{left}" y="{top}" width="{right - left}" '
        f'height="{bottom - top}" rx="{rect.radius}" fill="{rect.fill}"/>'
    )


def _svg_polyline(line: Polyline) -> str:
    commands = " L".join(f"{x} {y}" for x, y in line.points)
    return (
        f'<path d="M{commands}" fill="none" stroke="{line.stroke}" '
        f'stroke-width="{line.width}" stroke-linecap="round" '
        'stroke-linejoin="round"/>'
    )


def _svg_bezier(curve: BezierPath) -> str:
    start = f"{curve.start[0]} {curve.start[1]}"
    segments = " ".join(
        f"C{control_1[0]} {control_1[1]} {control_2[0]} {control_2[1]} "
        f"{end[0]} {end[1]}"
        for control_1, control_2, end in curve.segments
    )
    return (
        f'<path d="M{start} {segments}" fill="none" stroke="{curve.stroke}" '
        f'stroke-width="{curve.width}" stroke-linecap="round"/>'
    )


def _svg_circle(circle: Circle) -> str:
    x, y = circle.center
    centerline_radius = circle.outer_radius - circle.outline_width // 2
    return (
        f'<circle cx="{x}" cy="{y}" r="{centerline_radius}" fill="{circle.fill}" '
        f'stroke="{circle.outline}" stroke-width="{circle.outline_width}"/>'
    )


def _svg() -> str:
    shapes = (
        _svg_rect(BRAND.tile),
        _svg_rect(BRAND.workspace),
        _svg_polyline(BRAND.axis),
        _svg_bezier(BRAND.curve),
        *(_svg_circle(point) for point in BRAND.points),
    )
    body = "\n".join(f"  {shape}" for shape in shapes)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {BRAND.canvas} {BRAND.canvas}">\n{body}\n</svg>\n'
    )


def _scale_point(point: Point, scale: float) -> Point:
    return round(point[0] * scale), round(point[1] * scale)


def _scale_box(box: Box, scale: float) -> tuple[int, ...]:
    return tuple(round(value * scale) for value in box)


def _rounded_line(
    draw: ImageDraw.ImageDraw,
    points: list[Point],
    *,
    fill: str,
    width: int,
) -> None:
    radius = width // 2
    draw.line(points, fill=fill, width=width, joint="curve")
    for x, y in (points[0], points[-1]):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)


def _curve_points(curve: BezierPath, scale: float) -> list[Point]:
    sampled: list[Point] = []
    p0 = curve.start
    for p1, p2, p3 in curve.segments:
        for step in range(33):
            t = step / 32
            u = 1 - t
            x = (
                u**3 * p0[0]
                + 3 * u**2 * t * p1[0]
                + 3 * u * t**2 * p2[0]
                + t**3 * p3[0]
            )
            y = (
                u**3 * p0[1]
                + 3 * u**2 * t * p1[1]
                + 3 * u * t**2 * p2[1]
                + t**3 * p3[1]
            )
            point = round(x * scale), round(y * scale)
            if not sampled or point != sampled[-1]:
                sampled.append(point)
        p0 = p3
    return sampled


def _draw_rect(draw: ImageDraw.ImageDraw, rect: RoundedRect, scale: float) -> None:
    draw.rounded_rectangle(
        _scale_box(rect.box, scale),
        radius=round(rect.radius * scale),
        fill=rect.fill,
    )


def _render_png(size: int) -> Image.Image:
    scale = size * SUPERSAMPLE / BRAND.canvas
    rendered_size = size * SUPERSAMPLE
    image = Image.new("RGBA", (rendered_size, rendered_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    _draw_rect(draw, BRAND.tile, scale)
    _draw_rect(draw, BRAND.workspace, scale)
    _rounded_line(
        draw,
        [_scale_point(point, scale) for point in BRAND.axis.points],
        fill=BRAND.axis.stroke,
        width=round(BRAND.axis.width * scale),
    )
    _rounded_line(
        draw,
        _curve_points(BRAND.curve, scale),
        fill=BRAND.curve.stroke,
        width=round(BRAND.curve.width * scale),
    )

    for point in BRAND.points:
        x, y = _scale_point(point.center, scale)
        radius = round(point.outer_radius * scale)
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=point.fill,
            outline=point.outline,
            width=round(point.outline_width * scale),
        )

    return image.resize((size, size), Image.Resampling.LANCZOS)


def _save_png(image: Image.Image, path: Path) -> None:
    image.save(
        path,
        format="PNG",
        optimize=False,
        compress_level=PNG_COMPRESSION_LEVEL,
    )


def render_assets(output_dir: Path) -> tuple[Image.Image, Image.Image]:
    """Write deterministic SVG and PNG brand assets to ``output_dir``."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "origin-automation-logo.svg").write_text(
        _svg(), encoding="utf-8", newline="\n"
    )
    logo = _render_png(512)
    composer = _render_png(128)
    _save_png(logo, output_dir / "origin-automation-logo.png")
    _save_png(composer, output_dir / "origin-automation-composer.png")
    return logo, composer


def _write_qa_sheet(root: Path, logo: Image.Image, composer: Image.Image) -> None:
    qa = Image.new("RGB", (1408, 768), "#E4E7EA")
    ImageDraw.Draw(qa).rectangle((704, 0, 1408, 768), fill="#20252B")
    for x, image in ((96, logo), (800, logo), (288, composer), (992, composer)):
        y = 48 if image.width == 512 else 608
        qa.paste(image, (x, y), image)
    path = root / "artifacts" / "brand" / "icon-qa.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    _save_png(qa, path)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    logo, composer = render_assets(root / "assets")
    _write_qa_sheet(root, logo, composer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
