"""Read-only health diagnostics for Origin and the Python runtime."""

from __future__ import annotations

import csv
import os
import platform
import struct
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterable
from importlib import metadata
from pathlib import Path
from typing import Any

from ..com.discovery import (
    OriginRegistration,
    choose_registration,
    compact_registration_summary,
    discover_registrations,
    executable_version,
)
from ..contracts import ResultEnvelope

REQUIRED_DISTRIBUTIONS = (
    "mcp",
    "numpy",
    "openpyxl",
    "pydantic",
    "psutil",
    "pywin32",
    "scipy",
    "xlrd",
)


def executable_bits(path: str) -> int | None:
    try:
        with Path(path).open("rb") as handle:
            handle.seek(0x3C)
            pe_offset = struct.unpack("<I", handle.read(4))[0]
            handle.seek(pe_offset + 4)
            machine = struct.unpack("<H", handle.read(2))[0]
        return {0x14C: 32, 0x8664: 64}.get(machine)
    except (OSError, struct.error):
        return 64 if Path(path).stem.lower().endswith("64") else None


def dependency_report() -> dict[str, dict[str, object]]:
    report: dict[str, dict[str, object]] = {}
    for distribution in REQUIRED_DISTRIBUTIONS:
        try:
            version = metadata.version(distribution)
        except metadata.PackageNotFoundError:
            version = None
        report[distribution] = {"available": version is not None, "version": version}
    return report


def count_origin_processes() -> int:
    try:
        import psutil

        return sum(
            1
            for process in psutil.process_iter(["name"])
            if Path(str(process.info.get("name", ""))).stem.lower() == "origin64"
        )
    except Exception:
        pass
    try:
        completed = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Origin64.exe", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return 0
    return sum(
        1
        for row in csv.reader(completed.stdout.splitlines())
        if row and row[0].strip().lower() == "origin64.exe"
    )


def find_origin_scheduled_tasks() -> list[str]:
    try:
        completed = subprocess.run(
            ["schtasks", "/Query", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    tasks: list[str] = []
    for row in csv.reader(completed.stdout.splitlines()):
        if not row:
            continue
        combined = " ".join(row).lower()
        if "origin" in combined or "cleanup watchdog" in combined:
            tasks.append(row[0])
    return sorted(set(tasks))


def build_health_report(
    *,
    registrations: Iterable[OriginRegistration],
    python_bits: int | None = None,
    active_origin_processes: int | None = None,
    scheduled_tasks: list[str] | None = None,
    version_lookup: Callable[[str], str | None] = executable_version,
) -> ResultEnvelope:
    started = time.perf_counter()
    registrations = list(registrations)
    selected = choose_registration(registrations)
    version = version_lookup(selected.server_path) if selected else None
    runtime_bits = python_bits or struct.calcsize("P") * 8
    origin_bits = executable_bits(selected.server_path) if selected else None
    dependencies = dependency_report()
    permissions = {
        "origin_executable_readable": bool(
            selected and os.access(selected.server_path, os.R_OK)
        ),
        "temp_directory_writable": os.access(tempfile.gettempdir(), os.W_OK),
    }
    bitness_compatible = origin_bits is None or runtime_bits == origin_bits
    warnings: list[str] = []
    if not selected:
        warnings.append("No available Origin COM LocalServer32 registration was found")
    if active_origin_processes is not None and active_origin_processes > 0:
        warnings.append(
            "An Origin process is already running; default owned mode will not attach to it"
        )
    if not bitness_compatible:
        warnings.append(
            f"Python is {runtime_bits}-bit but the registered Origin executable is {origin_bits}-bit"
        )
    missing_dependencies = [
        name for name, status in dependencies.items() if not status["available"]
    ]
    if missing_dependencies:
        warnings.append(f"Missing Python dependencies: {', '.join(missing_dependencies)}")
    if not permissions["temp_directory_writable"]:
        warnings.append("The current account cannot write to the temporary directory")
    tasks = list(scheduled_tasks) if scheduled_tasks is not None else find_origin_scheduled_tasks()
    if tasks:
        warnings.append(
            "Origin-related scheduled tasks were found; inspect watchdog or cleanup tasks before long hidden COM sessions"
        )
    data: dict[str, Any] = {
        "healthy": bool(
            selected
            and bitness_compatible
            and all(status["available"] for status in dependencies.values())
            and permissions["origin_executable_readable"]
            and permissions["temp_directory_writable"]
        ),
        "platform": platform.platform(),
        "python_executable": sys.executable,
        "python_bits": runtime_bits,
        "origin_bits": origin_bits,
        "bitness_compatible": bitness_compatible,
        "dependencies": dependencies,
        "permissions": permissions,
        "registrations": compact_registration_summary(registrations),
        "selected_progid": selected.progid if selected else None,
        "selected_clsid": selected.clsid if selected else None,
        "selected_server_path": selected.server_path if selected else None,
        "selected_registry_view": selected.registry_view if selected else None,
        "active_origin_processes": active_origin_processes
        if active_origin_processes is not None
        else count_origin_processes(),
        "scheduled_tasks": tasks,
        "com_activation_tested": False,
    }
    duration_ms = int((time.perf_counter() - started) * 1000)
    return ResultEnvelope.ok(
        data,
        warnings=warnings,
        duration_ms=duration_ms,
        origin_version=version,
    )


def health_check() -> ResultEnvelope:
    return build_health_report(registrations=discover_registrations())
