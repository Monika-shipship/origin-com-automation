import pytest

from origin_com_automation.com.errors import AttachedSessionProtectedError
from origin_com_automation.com.session import SessionManager


def test_only_owned_session_can_be_shutdown():
    manager = SessionManager()
    owned = manager.register(progid="Origin.Application", pid=12, owned=True)
    attached = manager.register(progid="Origin.ApplicationSI", pid=34, owned=False)
    closed = []

    manager.shutdown(owned.session_id, lambda: closed.append(owned.session_id))

    assert closed == [owned.session_id]
    assert manager.get(owned.session_id).active is False

    with pytest.raises(AttachedSessionProtectedError):
        manager.shutdown(attached.session_id, lambda: closed.append(attached.session_id))

    assert closed == [owned.session_id]
