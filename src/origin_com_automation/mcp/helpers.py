"""Pure MCP schema and parameter helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..native.common import FileRef, RangeRef
from .schemas import NativeFileInput, NativeParameterInput, NativeRangeInput


def decode_native_parameter(value: NativeParameterInput) -> Any:
    if isinstance(value, NativeRangeInput):
        return RangeRef(value.value)
    if isinstance(value, NativeFileInput):
        return FileRef(value.value)
    return value.value


def inline_local_schema_refs(schema: dict[str, Any]) -> dict[str, Any]:
    definitions = schema.get("$defs", {})

    def expand(value: Any, stack: tuple[str, ...] = ()) -> Any:
        if isinstance(value, list):
            return [expand(item, stack) for item in value]
        if not isinstance(value, dict):
            return value
        ref = value.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            name = ref.rsplit("/", 1)[-1]
            if name not in stack and name in definitions:
                replacement = deepcopy(definitions[name])
                replacement.update({key: item for key, item in value.items() if key != "$ref"})
                return expand(replacement, (*stack, name))
        return {key: expand(item, stack) for key, item in value.items() if key != "$defs"}

    return expand(schema)
