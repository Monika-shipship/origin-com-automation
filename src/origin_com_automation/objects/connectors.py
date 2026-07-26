"""Validated Data Connector lifecycle plans."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .validation import ObjectPlanError, stable_ref


def connector_type_for_source(source: str | Path) -> str:
    """Return the Origin local-file connector family for a source path."""

    suffix = Path(source).suffix.lower()
    if suffix in {".csv", ".tsv"}:
        return "csv"
    if suffix in {".xls", ".xlsx", ".xlsm"}:
        return "excel"
    raise ObjectPlanError(
        f"source extension is not connector-supported: {suffix or '<none>'}"
    )


@dataclass(frozen=True)
class ConnectorPlan:
    action: str
    worksheet_ref: str
    source: Path | None
    connector_type: str | None
    keep_connector: bool
    keep_data: bool | None
    verification: str


def build_connector_plan(
    *,
    action: str,
    worksheet_ref: str,
    source: str | None = None,
    connector_type: str | None = None,
    keep_connector: bool = True,
    keep_data: bool | None = None,
) -> ConnectorPlan:
    normalized_action = action.strip().lower()
    if normalized_action not in {"create", "info", "refresh", "disconnect"}:
        raise ObjectPlanError("connector action must be create, info, refresh, or disconnect")
    target = stable_ref(worksheet_ref, kind="worksheet ref")
    resolved_source: Path | None = None
    normalized_type = connector_type.lower() if connector_type else None
    if normalized_action == "create":
        if normalized_type not in {"csv", "excel"}:
            raise ObjectPlanError("connector_type must be csv or excel")
        if not source:
            raise ObjectPlanError("connector create requires source")
        resolved_source = Path(source).expanduser().resolve()
        if not resolved_source.is_file():
            raise ObjectPlanError(f"connector source does not exist: {resolved_source}")
        expected = {".csv", ".tsv"} if normalized_type == "csv" else {".xls", ".xlsx", ".xlsm"}
        if resolved_source.suffix.lower() not in expected:
            raise ObjectPlanError("source extension does not match connector_type")
    elif source is not None or connector_type is not None:
        raise ObjectPlanError(f"connector {normalized_action} does not accept source or connector_type")
    if normalized_action == "disconnect" and keep_data is None:
        raise ObjectPlanError("connector disconnect requires explicit keep_data")
    return ConnectorPlan(
        action=normalized_action,
        worksheet_ref=target,
        source=resolved_source,
        connector_type=normalized_type,
        keep_connector=bool(keep_connector),
        keep_data=keep_data,
        verification="connector_state_and_source",
    )
