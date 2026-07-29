"""Read-only discovery of Origin COM registrations and installed binaries."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

KNOWN_PROGIDS = (
    "Origin.Application",
    "Origin.ApplicationCOMSI",
    "Origin.ApplicationSI",
)


@dataclass(frozen=True)
class OriginRegistration:
    progid: str
    clsid: str
    server_path: str
    registry_view: str

    @property
    def available(self) -> bool:
        return Path(self.server_path).expanduser().exists()


def _normalise_server_path(value: str | None) -> str:
    if not value:
        return ""
    value = os.path.expandvars(value.strip())
    if value.startswith('"') and '"' in value[1:]:
        value = value[1 : value.find('"', 1)]
    else:
        value = value.split(" /", 1)[0].strip()
    return os.path.normpath(value)


def choose_registration(
    registrations: Iterable[OriginRegistration],
) -> OriginRegistration | None:
    """Choose an available registration without activating COM."""

    available = [registration for registration in registrations if registration.available]
    if not available:
        return None
    priority = {progid: index for index, progid in enumerate(KNOWN_PROGIDS)}
    available.sort(key=lambda item: (priority.get(item.progid, 99), item.registry_view))
    return available[0]


def _read_registry_value(winreg_module, root, key: str, *, view: int) -> str | None:
    flags = winreg_module.KEY_READ | view
    try:
        with winreg_module.OpenKey(root, key, 0, flags) as handle:
            return winreg_module.QueryValueEx(handle, "")[0]
    except OSError:
        return None


def discover_registrations() -> list[OriginRegistration]:
    """Inspect both Windows registry views and return Origin COM candidates."""

    try:
        import winreg
    except ImportError:
        return []

    registrations: list[OriginRegistration] = []
    views = (("64", getattr(winreg, "KEY_WOW64_64KEY", 0)), ("32", getattr(winreg, "KEY_WOW64_32KEY", 0)))
    for view_name, view_flag in views:
        for progid in KNOWN_PROGIDS:
            clsid = _read_registry_value(winreg, winreg.HKEY_CLASSES_ROOT, f"{progid}\\CLSID", view=view_flag)
            if not clsid:
                continue
            server = _read_registry_value(
                winreg,
                winreg.HKEY_CLASSES_ROOT,
                f"CLSID\\{clsid}\\LocalServer32",
                view=view_flag,
            )
            if server:
                registrations.append(
                    OriginRegistration(
                        progid=progid,
                        clsid=str(clsid),
                        server_path=_normalise_server_path(str(server)),
                        registry_view=view_name,
                    )
                )
    return registrations


def executable_version(path: str) -> str | None:
    """Read a Windows file version when pywin32 is available."""

    try:
        import win32api

        info = win32api.GetFileVersionInfo(path, "\\")
        ms = info["FileVersionMS"]
        ls = info["FileVersionLS"]
        return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"
    except Exception:
        return None


def compact_registration_summary(registrations: Iterable[OriginRegistration]) -> list[dict[str, object]]:
    return [
        {
            "progid": item.progid,
            "clsid": item.clsid,
            "server_path": item.server_path,
            "registry_view": item.registry_view,
            "available": item.available,
            "version": executable_version(item.server_path) if item.available else None,
        }
        for item in registrations
    ]
