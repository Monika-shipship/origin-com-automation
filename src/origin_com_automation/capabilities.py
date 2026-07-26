"""Version-aware feature catalog for the Origin automation surface."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

CapabilityStatus = Literal["verified", "supported_unverified", "unsupported"]


@dataclass(frozen=True)
class Capability:
    name: str
    status: CapabilityStatus
    min_origin: str | None = None
    notes: str | None = None


CAPABILITIES: tuple[Capability, ...] = (
    Capability("session.owned_background", "verified", notes="Serialized STA COM session."),
    Capability("session.read_only_attach", "verified"),
    Capability(
        "session.force_quit",
        "unsupported",
        notes="PID observation does not prove COM proxy ownership.",
    ),
    Capability("data.csv_excel_import", "verified"),
    Capability("data.source_preflight", "verified"),
    Capability("connector.local_file", "supported_unverified"),
    Capability("connector.remote_authenticated", "unsupported"),
    Capability("matrix.read_write", "supported_unverified"),
    Capability("matrix.transform", "supported_unverified"),
    Capability("image.import_convert", "supported_unverified"),
    Capability("analysis.python_structured", "verified"),
    Capability("analysis.xfunction", "supported_unverified"),
    Capability("analysis.native_operation", "supported_unverified"),
    Capability("graph.scatter", "verified"),
    Capability("graph.line", "verified"),
    Capability("graph.column", "verified"),
    Capability("graph.errorbar", "supported_unverified"),
    Capability("graph.heatmap", "supported_unverified"),
    Capability("graph.contour", "supported_unverified"),
    Capability("graph.three_d", "supported_unverified"),
    Capability("graph.polar", "supported_unverified"),
    Capability("graph.ternary", "supported_unverified"),
    Capability("graph.preview", "supported_unverified"),
    Capability("project.folders_notes", "supported_unverified"),
    Capability("workflow.figurespec", "supported_unverified"),
    Capability("workflow.serial_batch", "supported_unverified"),
)


def capability_report(
    origin_version: str | None,
    *,
    domain: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Return stable capability metadata, optionally limited to one domain."""

    prefix = f"{domain.strip().lower()}." if domain else None
    selected = (
        item for item in CAPABILITIES if prefix is None or item.name.startswith(prefix)
    )
    return {
        item.name: {**asdict(item), "detected_origin": origin_version}
        for item in selected
    }
