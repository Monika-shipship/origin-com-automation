"""Strict LabTalk values shared by native Origin command planners."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class NativeValidationError(ValueError):
    """A native command could not be made safe and deterministic."""

    code = "NATIVE_VALIDATION_FAILED"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


_UNSAFE_REF = re.compile(r'[;"\r\n{}]')
_UNSAFE_STRING = re.compile(r'[;"\r\n{}]')


def _validate_reference(value: str, kind: str) -> str:
    normalized = value.strip()
    if not normalized or _UNSAFE_REF.search(normalized):
        raise NativeValidationError(f"unsafe {kind}: {value!r}")
    return normalized


@dataclass(frozen=True)
class RangeRef:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _validate_reference(self.value, "range ref"))


@dataclass(frozen=True)
class OutputRef:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _validate_reference(self.value, "output ref"))


@dataclass(frozen=True)
class FileRef:
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.replace("\\", "/").strip()
        if not normalized or _UNSAFE_STRING.search(normalized):
            raise NativeValidationError(f"unsafe file path: {self.value!r}")
        object.__setattr__(self, "value", normalized)


def labtalk_literal(value: Any) -> str:
    """Serialize a restricted Python/native value into one LabTalk token."""

    if isinstance(value, (RangeRef, OutputRef)):
        return value.value
    if isinstance(value, FileRef):
        return f'"{value.value}"'
    if isinstance(value, Path):
        return labtalk_literal(FileRef(str(value)))
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise NativeValidationError("native numeric parameters must be finite")
        return format(value, ".15g")
    if isinstance(value, str):
        if _UNSAFE_STRING.search(value):
            raise NativeValidationError(f"unsafe LabTalk string: {value!r}")
        return f'"{value}"'
    if isinstance(value, (list, tuple)):
        if not value:
            raise NativeValidationError("native parameter lists cannot be empty")
        return " ".join(labtalk_literal(item) for item in value)
    raise NativeValidationError(f"unsupported native parameter type: {type(value).__name__}")


def validate_identifier(value: str, *, kind: str = "identifier") -> str:
    normalized = value.strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9_]*", normalized):
        raise NativeValidationError(f"invalid {kind}: {value!r}")
    return normalized

