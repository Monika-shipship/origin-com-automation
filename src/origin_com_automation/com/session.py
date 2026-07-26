"""Ownership-aware Origin session records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from uuid import uuid4

from .errors import AttachedSessionProtectedError, SessionNotFoundError


@dataclass
class SessionRecord:
    session_id: str
    progid: str
    pid: int | None
    owned: bool
    visible: bool
    active: bool = True
    project_path: str | None = None


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionRecord] = {}

    def register(
        self,
        *,
        progid: str,
        pid: int | None,
        owned: bool,
        visible: bool = False,
        project_path: str | None = None,
    ) -> SessionRecord:
        record = SessionRecord(
            session_id=uuid4().hex,
            progid=progid,
            pid=pid,
            owned=owned,
            visible=visible,
            project_path=project_path,
        )
        self._sessions[record.session_id] = record
        return record

    def get(self, session_id: str) -> SessionRecord:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise SessionNotFoundError(f"Unknown Origin session: {session_id}") from exc

    def list_active(self) -> list[SessionRecord]:
        return [record for record in self._sessions.values() if record.active]

    def shutdown(self, session_id: str, close_fn: Callable[[], None]) -> None:
        record = self.get(session_id)
        if not record.owned:
            raise AttachedSessionProtectedError(
                "The session is attached to a user-owned Origin instance and cannot be shut down"
            )
        close_fn()
        record.active = False

    def detach(self, session_id: str) -> None:
        self.get(session_id).active = False
