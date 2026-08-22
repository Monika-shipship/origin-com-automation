"""Version-aware feature catalog for the Origin automation surface."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
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
    Capability(
        "data.linked_local_import",
        "verified",
        notes="CSV and Excel imports default to persistent local Data Connectors with source hash and cell-profile validation.",
    ),
    Capability("connector.local_file", "verified", notes="CSV create, refresh, and disconnect on Origin 10.1."),
    Capability("connector.remote_authenticated", "unsupported"),
    Capability("matrix.read_write", "verified", notes="Create, rectangular write, readback, and OPJU reopen on Origin 10.1."),
    Capability("matrix.transform", "supported_unverified"),
    Capability(
        "image.import",
        "verified",
        min_origin="9.85",
        notes="Real Image Page create/import requires Origin 2021b; live-verified on Origin 10.1.",
    ),
    Capability("image.export_convert", "supported_unverified"),
    Capability("analysis.python_structured", "verified"),
    Capability(
        "analysis.python_explicit",
        "verified",
        notes="Explicit compatibility backend; results are labeled non-recalculating in Origin.",
    ),
    Capability("analysis.xfunction", "supported_unverified"),
    Capability("analysis.native_operation", "supported_unverified"),
    Capability(
        "analysis.xfunction_fitlr",
        "verified",
        notes="Structured fitlr invocation with dynamic output resolution on Origin 10.1.",
    ),
    Capability(
        "analysis.native_operation_fitlr",
        "verified",
        notes="Create, query, change input, recalculate, and verify output on Origin 10.1.",
    ),
    Capability(
        "analysis.native_default_fitlr",
        "verified",
        notes="Default linear fit creates an auto-recalculating Origin fitlr Analysis Operation.",
    ),
    Capability(
        "worksheet.origin_formula",
        "verified",
        notes="csetvalue F(x) formula, script, range, SVRM, and values verified on Origin 10.1.",
    ),
    Capability("graph.scatter", "verified"),
    Capability("graph.line", "verified"),
    Capability("graph.column", "verified"),
    Capability("graph.errorbar", "supported_unverified"),
    Capability("graph.heatmap", "supported_unverified"),
    Capability("graph.contour", "supported_unverified"),
    Capability("graph.three_d", "supported_unverified"),
    Capability("graph.polar", "supported_unverified"),
    Capability("graph.ternary", "supported_unverified"),
    Capability("graph.preview", "verified", notes="PNG preview and pixel metrics on Origin 10.1."),
    Capability("project.folder_create_list_rename", "verified"),
    Capability("project.folder_move", "supported_unverified"),
    Capability("project.folder_delete", "supported_unverified"),
    Capability("project.note_create_write_info", "verified"),
    Capability("project.note_export", "supported_unverified"),
    Capability("project.note_delete", "supported_unverified"),
    Capability("workflow.figurespec", "verified", notes="Data-to-project route with editable OPJU, PNG export, QA, and shutdown."),
    Capability("workflow.serial_batch", "verified", notes="Two-item serialized FigureSpec smoke on Origin 10.1."),
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
    detected_numbers = re.findall(r"\d+", origin_version or "")
    detected = (
        (int(detected_numbers[0]), int(detected_numbers[1]))
        if len(detected_numbers) >= 2
        else None
    )

    def reported(item: Capability) -> dict[str, Any]:
        data = {**asdict(item), "detected_origin": origin_version}
        if item.min_origin:
            minimum_numbers = re.findall(r"\d+", item.min_origin)
            minimum = (
                (int(minimum_numbers[0]), int(minimum_numbers[1]))
                if len(minimum_numbers) >= 2
                else None
            )
            if detected is None or minimum is None or detected < minimum:
                data["status"] = "unsupported"
                data["version_gate_applied"] = True
        return data

    return {item.name: reported(item) for item in selected}
