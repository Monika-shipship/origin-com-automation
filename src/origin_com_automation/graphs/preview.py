"""PNG preview metrics and expected-color pixel checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def _rgb(hex_color: str) -> np.ndarray:
    value = hex_color.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"invalid expected color: {hex_color}")
    return np.asarray([int(value[index:index + 2], 16) for index in (0, 2, 4)])


def inspect_png(
    path: str | Path,
    expected_colors: list[str] | None = None,
    tolerance: int = 12,
    edge_margin: int = 1,
    maximum_whitespace_ratio: float = 0.97,
) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"PNG does not exist: {source}")
    if source.suffix.lower() != ".png":
        raise ValueError("preview inspection requires PNG")
    if tolerance < 0 or tolerance > 255:
        raise ValueError("color tolerance must be between 0 and 255")
    if edge_margin < 0:
        raise ValueError("edge_margin must be non-negative")
    if not 0 <= maximum_whitespace_ratio <= 1:
        raise ValueError("maximum_whitespace_ratio must be between 0 and 1")
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
    nonblank_ratio = float(np.count_nonzero(nonblank) / total)
    whitespace_ratio = 1.0 - nonblank_ratio
    touches_edge = bool(
        bbox
        and (
            bbox[0] <= edge_margin
            or bbox[1] <= edge_margin
            or bbox[2] >= image.width - 1 - edge_margin
            or bbox[3] >= image.height - 1 - edge_margin
        )
    )
    extreme_whitespace = bool(coordinates.size and whitespace_ratio > maximum_whitespace_ratio)
    suspected_clipping = touches_edge or extreme_whitespace
    qa_warnings = []
    if touches_edge:
        qa_warnings.append("Visible content touches the configured canvas edge margin")
    if extreme_whitespace:
        qa_warnings.append("Visible content occupies too little of the canvas")
    if not coordinates.size:
        qa_warnings.append("Preview is blank")
    return {
        "path": str(source),
        "dimensions": [image.width, image.height],
        "nonblank_ratio": nonblank_ratio,
        "alpha_coverage": float(np.count_nonzero(visible) / total),
        "unique_color_count": int(unique_colors),
        "content_bbox": bbox,
        "expected_color_pixels": expected_counts,
        "file_size": source.stat().st_size,
        "whitespace_ratio": whitespace_ratio,
        "content_touches_edge": touches_edge,
        "suspected_clipping": suspected_clipping,
        "qa_passed": bool(coordinates.size) and not suspected_clipping,
        "qa_warnings": qa_warnings,
    }
