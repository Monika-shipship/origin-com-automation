"""Image Page import/export plans."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .validation import ObjectPlanError, stable_ref


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


@dataclass(frozen=True)
class ImagePlan:
    action: str
    image_ref: str
    path: Path | None
    overwrite: bool
    verification: str


def build_image_plan(
    *,
    action: str,
    image_ref: str,
    path: str | None = None,
    overwrite: bool = False,
    max_bytes: int = 100 * 1024 * 1024,
) -> ImagePlan:
    normalized_action = action.strip().lower()
    if normalized_action not in {"create", "info", "import", "export", "delete"}:
        raise ObjectPlanError(
            "image action must be create, info, import, export, or delete"
        )
    target = stable_ref(image_ref, kind="image ref")
    resolved: Path | None = None
    if normalized_action in {"import", "export"}:
        if not path:
            raise ObjectPlanError(f"image {normalized_action} requires path")
        resolved = Path(path).expanduser().resolve()
        if resolved.suffix.lower() not in IMAGE_EXTENSIONS:
            raise ObjectPlanError("image path extension is not supported")
        if normalized_action == "import":
            if not resolved.is_file():
                raise ObjectPlanError(f"image source does not exist: {resolved}")
            if resolved.stat().st_size > max_bytes:
                raise ObjectPlanError("image payload limit exceeded")
        else:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            if resolved.exists() and not overwrite:
                raise ObjectPlanError(f"image export already exists: {resolved}")
    elif path is not None:
        raise ObjectPlanError(f"image {normalized_action} does not accept path")
    return ImagePlan(
        action=normalized_action,
        image_ref=target,
        path=resolved,
        overwrite=overwrite,
        verification="page_state_and_artifact" if normalized_action == "export" else "page_state",
    )
