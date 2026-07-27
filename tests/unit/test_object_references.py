import pytest

from origin_com_automation.objects.references import (
    ObjectRef,
    ObjectReferenceError,
    ObjectRefRegistry,
)


def test_registry_tracks_aliases_when_origin_renames_object():
    registry = ObjectRefRegistry(session_id="session-a")
    original = registry.register(
        kind="worksheet",
        logical_id="worksheet:data",
        internal_name="Data",
        container_logical_id="workbook:book1",
        long_name="Measurement Data",
        folder_path="/Analysis",
    )

    renamed = registry.rename(original.logical_id, "Data2")

    assert renamed.internal_name == "Data2"
    assert renamed.aliases == ("Data",)
    assert renamed.generation == 1
    assert registry.resolve("worksheet:data") == renamed
    assert registry.resolve_identifier(kind="worksheet", identifier="Data") == renamed
    assert registry.resolve_identifier(kind="worksheet", identifier="Data2") == renamed


def test_registry_rejects_cross_session_refs():
    registry = ObjectRefRegistry(session_id="session-a")
    foreign = ObjectRef(
        kind="graph",
        session_id="session-b",
        logical_id="graph:g1",
        internal_name="Graph1",
    )

    with pytest.raises(ObjectReferenceError, match="session"):
        registry.resolve(foreign)


def test_rebind_uses_fingerprint_but_fails_closed_on_ambiguity():
    registry = ObjectRefRegistry(session_id="session-a")
    reference = registry.register(
        kind="worksheet",
        logical_id="worksheet:data",
        internal_name="Data",
        long_name="Transfer Curve",
        folder_path="/Results",
        stability="rebindable",
    )
    candidates = [
        {
            "kind": "worksheet",
            "internal_name": "Sheet1",
            "long_name": "Transfer Curve",
            "folder_path": "/Results",
        },
        {
            "kind": "worksheet",
            "internal_name": "Sheet2",
            "long_name": "Transfer Curve",
            "folder_path": "/Results",
        },
    ]

    with pytest.raises(ObjectReferenceError, match="ambiguous"):
        registry.rebind(reference.logical_id, candidates)

    rebound = registry.rebind(reference.logical_id, candidates[:1])
    assert rebound.internal_name == "Sheet1"
    assert "Data" in rebound.aliases
    assert rebound.verification_state == "rebound"


def test_registry_round_trip_contains_no_runtime_proxy_objects():
    registry = ObjectRefRegistry(session_id="session-a")
    registry.register(
        kind="analysis_operation",
        logical_id="analysis:fit",
        internal_name="op://fitlr/abc",
        stability="session_stable",
    )

    payload = registry.export()
    restored = ObjectRefRegistry.from_export(payload)

    assert payload["session_id"] == "session-a"
    assert restored.resolve("analysis:fit").internal_name == "op://fitlr/abc"
    assert restored.export() == payload
