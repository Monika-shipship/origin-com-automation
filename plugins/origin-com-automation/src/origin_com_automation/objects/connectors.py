"""Validated Data Connector lifecycle plans."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

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
    selection: str | None
    has_header: bool | None
    verification: str


def _header_node(root: ElementTree.Element, connector_type: str) -> ElementTree.Element:
    path = "./Settings/heading" if connector_type == "csv" else "./Settings/labels/longname"
    node = root.find(path)
    if node is None:
        raise ObjectPlanError(
            f"Origin {connector_type} connector options do not expose a header setting"
        )
    return node


def connector_options_with_header(
    options: str, *, connector_type: str, has_header: bool
) -> str:
    """Set the persistent Origin Connector header option without string patching."""

    if connector_type not in {"csv", "excel"}:
        raise ObjectPlanError("connector_type must be csv or excel")
    try:
        root = ElementTree.fromstring(options)
    except ElementTree.ParseError as exc:
        raise ObjectPlanError("Origin connector options are not valid XML") from exc
    value = "1" if has_header else "0"
    _header_node(root, connector_type).text = value
    if connector_type == "excel":
        main_header = root.find("./Settings/mainheader")
        labels = root.find("./Settings/labels")
        if main_header is None or labels is None:
            raise ObjectPlanError(
                "Origin excel connector options do not expose mainheader and labels"
            )
        main_header.text = "0"
        labels.set("Use", value)
    return ElementTree.tostring(root, encoding="unicode", short_empty_elements=True)


def connector_header_state(options: str, *, connector_type: str) -> bool:
    try:
        root = ElementTree.fromstring(options)
    except ElementTree.ParseError as exc:
        raise ObjectPlanError("Origin connector options are not valid XML") from exc
    state = (_header_node(root, connector_type).text or "0").strip() == "1"
    if connector_type == "excel":
        main_header = root.find("./Settings/mainheader")
        labels = root.find("./Settings/labels")
        if main_header is None or labels is None:
            raise ObjectPlanError(
                "Origin excel connector options do not expose mainheader and labels"
            )
        state = (
            state
            and labels.get("Use", "0").strip() == "1"
            and (main_header.text or "0").strip() == "0"
        )
    return state


def build_connector_plan(
    *,
    action: str,
    worksheet_ref: str,
    source: str | None = None,
    connector_type: str | None = None,
    keep_connector: bool = True,
    keep_data: bool | None = None,
    selection: str | None = None,
    has_header: bool | None = None,
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
        normalized_selection = selection.strip() if selection is not None else None
        if normalized_selection is not None and (
            not normalized_selection
            or any(character in normalized_selection for character in "\x00\r\n")
        ):
            raise ObjectPlanError("connector selection must be a non-empty single line")
    elif source is not None or connector_type is not None:
        raise ObjectPlanError(f"connector {normalized_action} does not accept source or connector_type")
    else:
        normalized_selection = None
    if normalized_action != "create" and (selection is not None or has_header is not None):
        raise ObjectPlanError("selection and has_header are only accepted for connector create")
    if normalized_action == "disconnect" and keep_data is None:
        raise ObjectPlanError("connector disconnect requires explicit keep_data")
    return ConnectorPlan(
        action=normalized_action,
        worksheet_ref=target,
        source=resolved_source,
        connector_type=normalized_type,
        keep_connector=bool(keep_connector),
        keep_data=keep_data,
        selection=normalized_selection,
        has_header=has_header,
        verification="connector_state_and_source",
    )
