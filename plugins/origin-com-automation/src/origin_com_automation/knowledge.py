"""Bounded query over original summaries and official Origin documentation links."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


def _entries() -> list[dict[str, Any]]:
    path = Path(__file__).with_name("resources") / "knowledge.json"
    return json.loads(path.read_text(encoding="utf-8"))


def query_knowledge(
    *,
    term: str | None = None,
    domain: str | None = None,
    status: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    if limit < 1 or limit > 100:
        raise ValueError("knowledge query limit must be between 1 and 100")
    needle = term.strip().casefold() if term else None
    results = []
    for item in _entries():
        if domain is not None and item["domain"] != domain:
            continue
        if status is not None and item["status"] != status:
            continue
        searchable = " ".join(
            [
                item["id"],
                item["title"],
                item["summary"],
                *item.get("keywords", []),
                *item.get("tools", []),
            ]
        ).casefold()
        if needle and needle not in searchable:
            continue
        results.append(deepcopy(item))
        if len(results) >= limit:
            break
    return results

