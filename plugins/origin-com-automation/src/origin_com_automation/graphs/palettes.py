"""Load the plugin-owned palette catalog."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


def palette_catalog() -> dict[str, dict[str, Any]]:
    path = Path(__file__).with_name("palettes.json")
    return deepcopy(json.loads(path.read_text(encoding="utf-8")))

