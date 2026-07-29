"""Output artifact validation for graph and project exports."""

from __future__ import annotations

from pathlib import Path

from .projects import validate_artifact


SUPPORTED_EXPORTS = {"png", "tif", "tiff", "pdf", "svg"}


def normalize_export_format(kind: str) -> str:
    normalized = kind.lower().lstrip(".")
    if normalized not in SUPPORTED_EXPORTS:
        raise ValueError(f"Unsupported graph export format: {kind}")
    return "tif" if normalized == "tiff" else normalized


def export_suffixes(kind: str) -> set[str]:
    normalized = normalize_export_format(kind)
    return {".tif", ".tiff"} if normalized == "tif" else {f".{normalized}"}


def _artifact_signature(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns


def snapshot_artifacts(directory: str | Path, stem: str) -> dict[Path, tuple[int, int]]:
    root = Path(directory).expanduser().resolve()
    if not root.is_dir():
        return {}
    result: dict[Path, tuple[int, int]] = {}
    for candidate in root.glob(f"{stem}*"):
        if candidate.is_file():
            resolved = candidate.resolve()
            result[resolved] = _artifact_signature(resolved)
    return result


def select_changed_artifact(
    directory: str | Path,
    stem: str,
    before: dict[Path, tuple[int, int]],
    *,
    suffixes: set[str],
) -> Path | None:
    root = Path(directory).expanduser().resolve()
    candidates: list[Path] = []
    for candidate in root.glob(f"{stem}*"):
        resolved = candidate.resolve()
        if resolved.suffix.lower() not in suffixes or not validate_artifact(resolved):
            continue
        if before.get(resolved) != _artifact_signature(resolved):
            candidates.append(resolved)
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.name), default=None)


def validate_export_path(path: str | Path, *, kind: str) -> Path:
    normalize_export_format(kind)
    output = Path(path).expanduser().resolve()
    if not validate_artifact(output):
        raise FileNotFoundError(f"Export artifact was not created or is empty: {output}")
    return output
