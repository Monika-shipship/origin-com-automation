"""Environment and safety defaults for the local Origin plugin."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PluginConfig:
    plugin_root: Path
    origin_progid: str | None = None
    visible: bool = False
    attach: bool = False
    operation_timeout_s: float = 60.0

    @classmethod
    def from_environment(cls, plugin_root: str | Path) -> "PluginConfig":
        def as_bool(value: str | None, default: bool) -> bool:
            if value is None:
                return default
            return value.strip().lower() in {"1", "true", "yes", "on"}

        raw_timeout = os.getenv("ORIGIN_OPERATION_TIMEOUT_S", "60")
        try:
            timeout = max(0.1, float(raw_timeout))
        except ValueError:
            timeout = 60.0
        return cls(
            plugin_root=Path(plugin_root).expanduser().resolve(),
            origin_progid=os.getenv("ORIGIN_PROGID") or None,
            visible=as_bool(os.getenv("ORIGIN_VISIBLE"), False),
            attach=as_bool(os.getenv("ORIGIN_ATTACH"), False),
            operation_timeout_s=timeout,
        )
