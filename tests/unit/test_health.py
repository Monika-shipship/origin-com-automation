from origin_com_automation.com.discovery import OriginRegistration
from origin_com_automation.tools.health import build_health_report


def test_health_report_is_read_only_and_identifies_selected_server(tmp_path):
    server = tmp_path / "Origin64.exe"
    server.write_bytes(b"fake")
    report = build_health_report(
        registrations=[
            OriginRegistration(
                progid="Origin.ApplicationSI",
                clsid="{si}",
                server_path=str(server),
                registry_view="32",
            )
        ],
        python_bits=64,
        active_origin_processes=1,
        scheduled_tasks=["\\Origin64 Cleanup Watchdog"],
        version_lookup=lambda _: "10.1.0.0",
    )

    payload = report.to_dict()

    assert payload["success"] is True
    assert payload["origin_version"] == "10.1.0.0"
    assert payload["data"]["selected_progid"] == "Origin.ApplicationSI"
    assert payload["data"]["active_origin_processes"] == 1
    assert payload["data"]["scheduled_tasks"] == ["\\Origin64 Cleanup Watchdog"]
    assert payload["data"]["origin_bits"] == 64
    assert payload["data"]["bitness_compatible"] is True
    assert payload["data"]["permissions"]["origin_executable_readable"] is True
    assert payload["data"]["dependencies"]["pywin32"]["available"] is True
    assert any("watchdog" in warning.lower() for warning in payload["warnings"])
    assert payload["data"]["com_activation_tested"] is False
