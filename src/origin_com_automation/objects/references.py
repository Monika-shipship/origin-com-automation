"""Structured session-scoped references for Origin project objects."""

from __future__ import annotations

from threading import RLock
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field


class ObjectReferenceError(LookupError):
    code = "OBJECT_REFERENCE_FAILED"


class ObjectRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str
    session_id: str
    logical_id: str
    internal_name: str
    container_logical_id: str | None = None
    long_name: str | None = None
    folder_path: str | None = None
    aliases: tuple[str, ...] = Field(default_factory=tuple)
    generation: int = Field(default=0, ge=0)
    stability: Literal["session_stable", "rebindable"] = "session_stable"
    verification_state: Literal["registered", "renamed", "rebound", "verified"] = (
        "registered"
    )


class ObjectRefRegistry:
    def __init__(self, *, session_id: str) -> None:
        normalized = session_id.strip()
        if not normalized:
            raise ObjectReferenceError("session_id must not be empty")
        self.session_id = normalized
        self._lock = RLock()
        self._refs: dict[str, ObjectRef] = {}

    def register(
        self,
        *,
        kind: str,
        logical_id: str,
        internal_name: str,
        container_logical_id: str | None = None,
        long_name: str | None = None,
        folder_path: str | None = None,
        stability: Literal["session_stable", "rebindable"] = "session_stable",
    ) -> ObjectRef:
        if not kind.strip() or not logical_id.strip() or not internal_name.strip():
            raise ObjectReferenceError(
                "kind, logical_id, and internal_name must not be empty"
            )
        with self._lock:
            if logical_id in self._refs:
                raise ObjectReferenceError(
                    f"logical object reference already exists: {logical_id}"
                )
            reference = ObjectRef(
                kind=kind.strip(),
                session_id=self.session_id,
                logical_id=logical_id.strip(),
                internal_name=internal_name.strip(),
                container_logical_id=(
                    container_logical_id.strip() if container_logical_id else None
                ),
                long_name=long_name,
                folder_path=folder_path,
                stability=stability,
            )
            self._refs[reference.logical_id] = reference
            return reference

    def resolve(self, reference: str | ObjectRef) -> ObjectRef:
        if isinstance(reference, ObjectRef):
            if reference.session_id != self.session_id:
                raise ObjectReferenceError(
                    "object reference belongs to a different Origin session"
                )
            logical_id = reference.logical_id
        else:
            logical_id = reference
        with self._lock:
            try:
                return self._refs[logical_id]
            except KeyError as exc:
                raise ObjectReferenceError(
                    f"unknown logical object reference: {logical_id}"
                ) from exc

    def resolve_identifier(self, *, kind: str, identifier: str) -> ObjectRef:
        normalized = identifier.strip().casefold()
        with self._lock:
            matches = [
                reference
                for reference in self._refs.values()
                if reference.kind == kind
                and normalized
                in {
                    reference.internal_name.casefold(),
                    *(alias.casefold() for alias in reference.aliases),
                }
            ]
        if not matches:
            raise ObjectReferenceError(f"no {kind} matches identifier: {identifier}")
        if len(matches) > 1:
            raise ObjectReferenceError(f"ambiguous {kind} identifier: {identifier}")
        return matches[0]

    def rename(self, logical_id: str, internal_name: str) -> ObjectRef:
        normalized = internal_name.strip()
        if not normalized:
            raise ObjectReferenceError("internal_name must not be empty")
        with self._lock:
            current = self.resolve(logical_id)
            if current.internal_name == normalized:
                return current
            aliases = tuple(dict.fromkeys((*current.aliases, current.internal_name)))
            updated = current.model_copy(
                update={
                    "internal_name": normalized,
                    "aliases": aliases,
                    "generation": current.generation + 1,
                    "verification_state": "renamed",
                }
            )
            self._refs[logical_id] = updated
            return updated

    def rebind(
        self,
        logical_id: str,
        candidates: list[Mapping[str, Any]],
    ) -> ObjectRef:
        with self._lock:
            current = self.resolve(logical_id)
            matches = [
                candidate
                for candidate in candidates
                if str(candidate.get("kind", "")) == current.kind
                and (
                    current.long_name is None
                    or candidate.get("long_name") == current.long_name
                )
                and (
                    current.folder_path is None
                    or candidate.get("folder_path") == current.folder_path
                )
            ]
            if not matches:
                raise ObjectReferenceError(
                    f"no fingerprint match for object reference: {logical_id}"
                )
            if len(matches) > 1:
                raise ObjectReferenceError(
                    f"ambiguous fingerprint match for object reference: {logical_id}"
                )
            internal_name = str(matches[0].get("internal_name", "")).strip()
            if not internal_name:
                raise ObjectReferenceError("rebind candidate has no internal_name")
            aliases = tuple(dict.fromkeys((*current.aliases, current.internal_name)))
            updated = current.model_copy(
                update={
                    "internal_name": internal_name,
                    "aliases": aliases,
                    "generation": current.generation + 1,
                    "verification_state": "rebound",
                }
            )
            self._refs[logical_id] = updated
            return updated

    def export(self) -> dict[str, Any]:
        with self._lock:
            return {
                "schema_version": 1,
                "session_id": self.session_id,
                "objects": [
                    self._refs[key].model_dump(mode="json")
                    for key in sorted(self._refs)
                ],
            }

    @classmethod
    def from_export(cls, payload: Mapping[str, Any]) -> "ObjectRefRegistry":
        if payload.get("schema_version") != 1:
            raise ObjectReferenceError("unsupported object reference export schema")
        registry = cls(session_id=str(payload.get("session_id", "")))
        for raw in payload.get("objects", []):
            reference = ObjectRef.model_validate(raw)
            if reference.session_id != registry.session_id:
                raise ObjectReferenceError(
                    "export contains an object from a different session"
                )
            if reference.logical_id in registry._refs:
                raise ObjectReferenceError(
                    f"duplicate logical object reference: {reference.logical_id}"
                )
            registry._refs[reference.logical_id] = reference
        return registry
