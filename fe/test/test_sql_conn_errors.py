import importlib
import pytest

from be.model import sql_conn


def test_get_database_url_requires_env(monkeypatch):
    monkeypatch.delenv("BOOKSTORE_DB_URL", raising=False)
    with pytest.raises(RuntimeError):
        sql_conn._get_database_url()


def test_session_scope_rollback(monkeypatch):
    class DummySession:
        def __init__(self):
            self.committed = False
            self.rolled = False
            self.closed = False

        def commit(self):
            self.committed = True

        def rollback(self):
            self.rolled = True

        def close(self):
            self.closed = True

    dummy_session = DummySession()

    monkeypatch.setattr(sql_conn, "SessionLocal", lambda: dummy_session)

    with pytest.raises(RuntimeError):
        with sql_conn.session_scope():
            raise RuntimeError("fail")

    assert dummy_session.rolled is True
    assert dummy_session.closed is True
    assert dummy_session.committed is False
