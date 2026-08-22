"""Conservative detection of Origin demo-license watermarks in graph exports."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def _runs(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    changes = np.diff(np.r_[False, mask, False].astype(np.int8))
    return np.where(changes == 1)[0], np.where(changes == -1)[0]


def _inspect_raster(path: Path) -> dict[str, Any]:
    pixels = np.asarray(Image.open(path).convert("RGB"))
    height, width = pixels.shape[:2]
    cyan = (
        (pixels[:, :, 0] <= 32)
        & (pixels[:, :, 1] >= 223)
        & (pixels[:, :, 2] >= 223)
    )
    ratio = float(np.count_nonzero(cyan) / cyan.size)
    row_counts = cyan.sum(axis=1)
    starts, ends = _runs(row_counts >= max(20, int(width * 0.03)))
    lengths = ends - starts
    substantial = lengths >= 10
    starts = starts[substantial]
    lengths = lengths[substantial]
    gaps = np.diff(starts)
    repeated_bands = (
        len(lengths) >= 5
        and float(np.median(lengths)) >= 10
        and float(np.std(lengths) / max(float(np.mean(lengths)), 1.0)) <= 0.15
        and len(gaps) >= 4
        and float(np.std(gaps) / max(float(np.mean(gaps)), 1.0)) <= 0.15
    )
    x_coverage = float(np.count_nonzero(cyan.any(axis=0)) / width)
    y_coverage = float(np.count_nonzero(cyan.any(axis=1)) / height)
    detected = (
        0.003 <= ratio <= 0.08
        and repeated_bands
        and x_coverage >= 0.15
        and y_coverage >= 0.10
    )
    return {
        "status": "detected" if detected else "not_detected",
        "detector": "origin_cyan_repeated_band_v1",
        "evidence": {
            "cyan_ratio": ratio,
            "repeated_band_count": int(len(lengths)),
            "median_band_height": float(np.median(lengths)) if len(lengths) else 0.0,
            "x_coverage": x_coverage,
            "y_coverage": y_coverage,
            "dimensions": [width, height],
        },
    }


def _inspect_pdf(path: Path) -> dict[str, Any]:
    executable = shutil.which("pdftotext")
    if not executable:
        return {"status": "indeterminate", "detector": "pdf_text_unavailable", "evidence": {"reason": "pdftotext is not installed"}}
    try:
        completed = subprocess.run(
            [executable, "-layout", str(path), "-"],
            capture_output=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"status": "indeterminate", "detector": "pdf_text_error", "evidence": {"reason": str(exc)}}
    if completed.returncode != 0:
        return {"status": "indeterminate", "detector": "pdf_text_error", "evidence": {"return_code": completed.returncode}}
    text = completed.stdout.decode("utf-8", errors="replace")
    occurrences = len(re.findall(r"d\s*e\s*m\s*o", text, flags=re.IGNORECASE))
    return {
        "status": "detected" if occurrences >= 3 else "not_detected",
        "detector": "origin_pdf_demo_text_v1",
        "evidence": {"demo_occurrences": occurrences},
    }


def inspect_export_watermark(path: str | Path) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    suffix = source.suffix.lower()
    try:
        if suffix in {".png", ".tif", ".tiff"}:
            return _inspect_raster(source)
        if suffix == ".pdf":
            return _inspect_pdf(source)
    except (OSError, ValueError) as exc:
        return {"status": "indeterminate", "detector": "artifact_decode_error", "evidence": {"reason": str(exc)}}
    return {"status": "indeterminate", "detector": "unsupported_artifact_type", "evidence": {"suffix": suffix}}
