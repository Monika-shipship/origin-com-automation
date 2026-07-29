"""Shared strict-model and controller metadata helpers."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Base model for user-authored contracts that reject unknown fields."""

    model_config = ConfigDict(extra="forbid")


def controller_origin_version(controller: Any, *, default: str | None = None) -> str | None:
    if controller is None:
        return default
    return getattr(controller, "origin_version", None) or getattr(
        controller, "_origin_version", None
    ) or default
