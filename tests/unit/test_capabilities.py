from origin_com_automation.capabilities import capability_report


def test_capabilities_distinguish_verified_unverified_and_unsupported_features():
    report = capability_report("10.1.0.178")

    assert report["graph.scatter"]["status"] == "verified"
    assert report["graph.ternary"]["status"] == "supported_unverified"
    assert report["session.force_quit"]["status"] == "unsupported"
    assert report["graph.scatter"]["detected_origin"] == "10.1.0.178"


def test_capabilities_filter_by_domain_without_losing_status_metadata():
    report = capability_report("10.1.0.178", domain="matrix")

    assert report
    assert all(name.startswith("matrix.") for name in report)
    assert all("status" in item and "notes" in item for item in report.values())


def test_capabilities_expose_verified_editable_native_defaults():
    report = capability_report("10.1.0.178")

    assert report["data.linked_local_import"]["status"] == "verified"
    assert report["worksheet.origin_formula"]["status"] == "verified"
    assert report["analysis.native_default_fitlr"]["status"] == "verified"
    assert report["analysis.python_explicit"]["status"] == "verified"
    assert "non-recalculating" in report["analysis.python_explicit"]["notes"]
