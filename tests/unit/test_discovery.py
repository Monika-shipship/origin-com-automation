from origin_com_automation.com.discovery import OriginRegistration, choose_registration


def test_choose_registration_prefers_available_known_server(tmp_path):
    server = tmp_path / "Origin64.exe"
    server.write_bytes(b"fake")
    candidates = [
        OriginRegistration(
            progid="Origin.ApplicationSI",
            clsid="{si}",
            server_path=str(tmp_path / "missing.exe"),
            registry_view="32",
        ),
        OriginRegistration(
            progid="Origin.Application",
            clsid="{app}",
            server_path=str(server),
            registry_view="32",
        ),
    ]

    selected = choose_registration(candidates)

    assert selected is not None
    assert selected.progid == "Origin.Application"
    assert selected.available is True


def test_choose_registration_returns_none_when_no_server_exists(tmp_path):
    selected = choose_registration(
        [
            OriginRegistration(
                progid="Origin.ApplicationSI",
                clsid="{si}",
                server_path=str(tmp_path / "missing.exe"),
                registry_view="64",
            )
        ]
    )

    assert selected is None
