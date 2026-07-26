"""Stable JSON contracts shared by MCP tools and service layers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Artifact:
    """A file or other user-facing output produced by an operation."""

    path: str
    kind: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class ResultEnvelope:
    """The response shape returned by every public service and MCP tool."""

    success: bool
    data: Any = None
    warnings: list[str] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    artifacts: list[Artifact] = field(default_factory=list)
    duration_ms: int | None = None
    origin_version: str | None = None

    @classmethod
    def ok(
        cls,
        data: Any = None,
        *,
        warnings: list[str] | None = None,
        artifacts: list[Artifact] | None = None,
        duration_ms: int | None = None,
        origin_version: str | None = None,
    ) -> "ResultEnvelope":
        return cls(
            success=True,
            data=data,
            warnings=list(warnings or []),
            artifacts=list(artifacts or []),
            duration_ms=duration_ms,
            origin_version=origin_version,
        )

    @classmethod
    def fail(
        cls,
        error_code: str,
        error_message: str,
        *,
        data: Any = None,
        warnings: list[str] | None = None,
        artifacts: list[Artifact] | None = None,
        duration_ms: int | None = None,
        origin_version: str | None = None,
    ) -> "ResultEnvelope":
        return cls(
            success=False,
            data=data,
            warnings=list(warnings or []),
            error_code=error_code,
            error_message=error_message,
            artifacts=list(artifacts or []),
            duration_ms=duration_ms,
            origin_version=origin_version,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "warnings": list(self.warnings),
            "error_code": self.error_code,
            "error_message": self.error_message,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "duration_ms": self.duration_ms,
            "origin_version": self.origin_version,
        }
