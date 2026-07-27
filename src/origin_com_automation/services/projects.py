"""Non-destructive Origin project file operations."""

from __future__ import annotations

import shutil
from pathlib import Path

from ..utils.hashing import sha256_file

MIN_PROJECT_SIZE_BYTES = 64


class SourceOverwriteError(ValueError):
    """Raised when a requested destination resolves to the source file."""


def copy_project(source: str | Path, target: str | Path, *, overwrite: bool = False) -> Path:
    source_path = Path(source).expanduser().resolve()
    target_path = Path(target).expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"Origin project does not exist: {source_path}")
    if source_path == target_path:
        raise SourceOverwriteError("The working copy destination must differ from the source project")
    if target_path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing output: {target_path}")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target_path)
    return target_path


def validate_artifact(path: str | Path) -> bool:
    artifact = Path(path).expanduser()
    return artifact.is_file() and artifact.stat().st_size > 0


def validate_project_artifact(path: str | Path) -> bool:
    artifact = Path(path).expanduser()
    return artifact.is_file() and artifact.stat().st_size >= MIN_PROJECT_SIZE_BYTES


def project_signature(path: str | Path) -> tuple[int, int, str] | None:
    artifact = Path(path).expanduser()
    if not artifact.is_file():
        return None
    stat = artifact.stat()
    return stat.st_size, stat.st_mtime_ns, sha256_file(artifact)
