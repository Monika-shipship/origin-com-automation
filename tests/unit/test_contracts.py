from origin_com_automation.contracts import Artifact, ResultEnvelope


def test_result_envelope_serializes_success_and_artifacts():
    result = ResultEnvelope.ok(
        {"rows": 3},
        warnings=["used a working copy"],
        artifacts=[Artifact(path="C:/out/plot.png", kind="plot")],
        origin_version="10.1",
        duration_ms=12,
    )

    payload = result.to_dict()

    assert payload["success"] is True
    assert payload["data"] == {"rows": 3}
    assert payload["warnings"] == ["used a working copy"]
    assert payload["artifacts"] == [{"path": "C:/out/plot.png", "kind": "plot"}]
    assert payload["origin_version"] == "10.1"
    assert payload["duration_ms"] == 12


def test_result_envelope_serializes_failure_without_fake_success():
    result = ResultEnvelope.fail("COM_TIMEOUT", "Origin did not respond")

    assert result.to_dict() == {
        "success": False,
        "data": None,
        "warnings": [],
        "error_code": "COM_TIMEOUT",
        "error_message": "Origin did not respond",
        "artifacts": [],
        "duration_ms": None,
        "origin_version": None,
    }
