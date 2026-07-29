"""Project Folder and Notes action plans."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .validation import stable_ref


class ProjectObjectError(ValueError):
    code = "PROJECT_OBJECT_INVALID"


def _project_path(value: str) -> str:
    normalized = "/" + str(PurePosixPath("/" + value.strip().lstrip("/"))).lstrip("/")
    if normalized == "/.":
        normalized = "/"
    if any(part in {".", ".."} for part in PurePosixPath(normalized).parts):
        raise ProjectObjectError("project path traversal is not allowed")
    if any(token in normalized for token in ('"', ";", "\n", "\r", "{" , "}")):
        raise ProjectObjectError("project path contains unsafe characters")
    return normalized


@dataclass(frozen=True)
class FolderPlan:
    action: str
    path: str
    destination: str | None
    parent_path: str
    name: str
    confirm_recursive: bool


def build_folder_plan(
    *,
    action: str,
    path: str,
    destination: str | None = None,
    nonempty: bool = False,
    confirm_recursive: bool = False,
) -> FolderPlan:
    normalized_action = action.strip().lower()
    if normalized_action not in {"list", "create", "move", "rename", "delete"}:
        raise ProjectObjectError("folder action must be list, create, move, rename, or delete")
    source = _project_path(path)
    if source == "/" and normalized_action in {"move", "rename", "delete"}:
        raise ProjectObjectError("the project root cannot be moved, renamed, or deleted")
    normalized_destination = None
    if normalized_action in {"move", "rename"}:
        if not destination:
            raise ProjectObjectError(f"folder {normalized_action} requires destination")
        normalized_destination = _project_path(destination)
        if normalized_destination == source:
            raise ProjectObjectError("folder destination must differ from source")
    elif destination is not None:
        raise ProjectObjectError(f"folder {normalized_action} does not accept destination")
    if normalized_action == "delete" and nonempty and not confirm_recursive:
        raise ProjectObjectError("non-empty folder delete requires confirm_recursive=true")
    pure = PurePosixPath(source)
    return FolderPlan(
        action=normalized_action,
        path=source,
        destination=normalized_destination,
        parent_path=str(pure.parent),
        name=pure.name,
        confirm_recursive=confirm_recursive,
    )


@dataclass(frozen=True)
class NotePlan:
    action: str
    note_ref: str
    text: str | None
    format: str
    path: Path | None
    overwrite: bool


def build_note_plan(
    *,
    action: str,
    note_ref: str,
    text: str | None = None,
    format: str = "text",
    path: str | None = None,
    overwrite: bool = False,
) -> NotePlan:
    normalized_action = action.strip().lower()
    if normalized_action not in {"info", "create", "write", "export", "delete"}:
        raise ProjectObjectError("note action must be info, create, write, export, or delete")
    target = stable_ref(note_ref, kind="note ref")
    normalized_format = format.strip().lower()
    if normalized_format not in {"text", "html"}:
        raise ProjectObjectError("note format must be text or html")
    if normalized_action in {"create", "write"} and text is None:
        raise ProjectObjectError(f"note {normalized_action} requires text")
    resolved = None
    if normalized_action == "export":
        if not path:
            raise ProjectObjectError("note export requires path")
        resolved = Path(path).expanduser().resolve()
        if resolved.suffix.lower() not in {".txt", ".html", ".htm"}:
            raise ProjectObjectError("note export extension must be .txt, .html, or .htm")
        if resolved.exists() and not overwrite:
            raise ProjectObjectError(f"note export already exists: {resolved}")
        resolved.parent.mkdir(parents=True, exist_ok=True)
    elif path is not None:
        raise ProjectObjectError(f"note {normalized_action} does not accept path")
    return NotePlan(
        action=normalized_action,
        note_ref=target,
        text=text,
        format=normalized_format,
        path=resolved,
        overwrite=overwrite,
    )

