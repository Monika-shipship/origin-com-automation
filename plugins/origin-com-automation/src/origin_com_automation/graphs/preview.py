"""PNG preview metrics and expected-color pixel checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from ..services.watermarks import inspect_export_watermark


def _rgb(hex_color: str) -> np.ndarray:
    value = hex_color.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"invalid expected color: {hex_color}")
    return np.asarray([int(value[index:index + 2], 16) for index in (0, 2, 4)])


def inspect_png(
    path: str | Path,
    expected_colors: list[str] | None = None,
    tolerance: int = 12,
) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"PNG does not exist: {source}")
    if source.suffix.lower() != ".png":
        raise ValueError("preview inspection requires PNG")
    if tolerance < 0 or tolerance > 255:
        raise ValueError("color tolerance must be between 0 and 255")
    image = Image.open(source).convert("RGBA")
    pixels = np.asarray(image)
    rgb = pixels[:, :, :3].astype(int)
    alpha = pixels[:, :, 3]
    visible = alpha > 0
    nonblank = visible & np.any(rgb != 255, axis=2)
    coordinates = np.argwhere(nonblank)
    bbox = None
    if coordinates.size:
        y_min, x_min = coordinates.min(axis=0)
        y_max, x_max = coordinates.max(axis=0)
        bbox = [int(x_min), int(y_min), int(x_max), int(y_max)]
    visible_rgb = pixels[:, :, :3][visible]
    unique_colors = len(np.unique(visible_rgb, axis=0)) if visible_rgb.size else 0
    expected_counts: dict[str, int] = {}
    for color in expected_colors or []:
        target = _rgb(color)
        difference = np.max(np.abs(rgb - target), axis=2)
        expected_counts[color] = int(np.count_nonzero(visible & (difference <= tolerance)))
    total = pixels.shape[0] * pixels.shape[1]
    return {
        "path": str(source),
        "dimensions": [image.width, image.height],
        "nonblank_ratio": float(np.count_nonzero(nonblank) / total),
        "alpha_coverage": float(np.count_nonzero(visible) / total),
        "unique_color_count": int(unique_colors),
        "content_bbox": bbox,
        "expected_color_pixels": expected_counts,
        "file_size": source.stat().st_size,
        "watermark": inspect_export_watermark(source),
    }

