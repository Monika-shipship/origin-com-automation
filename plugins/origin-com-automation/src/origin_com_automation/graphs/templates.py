"""Explicit graph template discovery and digest-locked application plans."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..objects.validation import stable_ref
from ..utils.hashing import sha256_file


class GraphTemplateError(ValueError):
    code = "GRAPH_TEMPLATE_INVALID"


_digest = sha256_file


def discover_templates(roots: list[str]) -> list[dict[str, object]]:
    templates: list[dict[str, object]] = []
    seen: set[Path] = set()
    for raw_root in roots:
        root = Path(raw_root).expanduser().resolve()
        if not root.is_dir():
            continue
        for path in sorted((*root.rglob("*.otp"), *root.rglob("*.otpu"))):
            resolved = path.resolve()
            if resolved in seen or root not in resolved.parents:
                continue
            seen.add(resolved)
            templates.append(
                {
                    "name": resolved.stem,
                    "path": str(resolved),
                    "extension": resolved.suffix.lower(),
                    "sha256": _digest(resolved),
                    "size": resolved.stat().st_size,
                }
            )
    return templates


@dataclass(frozen=True)
class TemplateApplicationPlan:
    graph_ref: str
    template_path: Path
    sha256: str
    required_layers: int | None
    command: str


def apply_template_plan(
    *,
    graph_ref: str,
    template_path: str,
    expected_sha256: str,
    required_layers: int | None = None,
    actual_layers: int | None = None,
) -> TemplateApplicationPlan:
    target = stable_ref(graph_ref, kind="graph ref")
    path = Path(template_path).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() not in {".otp", ".otpu"}:
        raise GraphTemplateError("graph template must be an existing .otp or .otpu file")
    digest = _digest(path)
    if digest.lower() != expected_sha256.lower():
        raise GraphTemplateError("graph template SHA-256 changed")
    if required_layers is not None:
        if required_layers < 1:
            raise GraphTemplateError("required_layers must be positive")
        if actual_layers is not None and actual_layers != required_layers:
            raise GraphTemplateError("graph template layer count is incompatible")
    return TemplateApplicationPlan(
        graph_ref=target,
        template_path=path,
        sha256=digest,
        required_layers=required_layers,
        command=f'template_apply file:="{path.as_posix()}";',
    )
