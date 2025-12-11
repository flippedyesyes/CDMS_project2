import uuid

import pytest

from be.model import error
from be.model.dao import user_dao
from be.model.user import User


class TestUserModelExtra:
    def setup_method(self):
        self.user_model = User()
        self.user_id = f"user_extra_{uuid.uuid4()}"
        self.password = "password"
        code, msg = self.user_model.register(self.user_id, self.password)
        assert code == 200, msg

    def test_check_token_invalid_jwt(self):
        code, msg, token = self.user_model.login(
            self.user_id, self.password, terminal="term"
        )
        assert code == 200, msg
        invalid_token = "invalid.token.payload"
        with self.user_model.session_scope() as session:
            db_user = user_dao.get_user(session, self.user_id, include_inactive=True)
            assert db_user is not None
            db_user.token = invalid_token
        code, msg = self.user_model.check_token(self.user_id, invalid_token)
        assert (code, msg) == error.error_authorization_fail()

    def test_register_revive_after_soft_delete(self):
        code, msg = self.user_model.unregister(self.user_id, self.password)
        assert code == 200, msg
        code, msg = self.user_model.register(self.user_id, self.password)
        assert code == 200, msg

    def test_logout_with_expired_token(self):
        code, msg, token = self.user_model.login(
            self.user_id, self.password, terminal="term"
        )
        assert code == 200, msg
        original_lifetime = User.token_lifetime
        try:
            User.token_lifetime = -1
            code, msg = self.user_model.logout(self.user_id, token)
            assert (code, msg) == error.error_authorization_fail()
        finally:
            User.token_lifetime = original_lifetime

    def test_login_update_token_failure(self, monkeypatch):
        def fake_update_token(session, user_id, token, terminal):
            return False

        monkeypatch.setattr(user_dao, "update_token", fake_update_token)
        code, msg, token = self.user_model.login(
            self.user_id, self.password, terminal="term"
        )
        assert (code, msg) == error.error_authorization_fail()
        assert token == ""

    def test_register_duplicate_user(self):
        code, msg = self.user_model.register(self.user_id, "new")
        assert (code, msg) == error.error_exist_user_id(self.user_id)

    def test_check_token_user_missing(self, monkeypatch):
        code, msg, token = self.user_model.login(
            self.user_id, self.password, terminal="term"
        )
        assert code == 200
        monkeypatch.setattr(
            user_dao, "get_user", lambda session, uid, include_inactive=False: None
        )
        code, msg = self.user_model.check_token(self.user_id, token)
        assert (code, msg) == error.error_authorization_fail()

    def test_change_password_update_failure(self, monkeypatch):
        def fake_update_password(session, user_id, new_pwd, token, terminal):
            return False

        monkeypatch.setattr(user_dao, "update_password", fake_update_password)
        code, msg = self.user_model.change_password(
            self.user_id, self.password, "new_password"
        )
        assert (code, msg) == error.error_authorization_fail()

    def test_unregister_soft_delete_failure(self, monkeypatch):
        def fake_soft_delete(session, user_id):
            return False

        monkeypatch.setattr(user_dao, "soft_delete_user", fake_soft_delete)
        code, msg = self.user_model.unregister(self.user_id, self.password)
        assert (code, msg) == error.error_authorization_fail()

    def test_logout_success(self, monkeypatch):
        code, msg, token = self.user_model.login(
            self.user_id, self.password, terminal="term"
        )
        assert code == 200

        called = {}

        def fake_update_token(session, user_id, token, terminal):
            called["user_id"] = user_id
            called["token"] = token
            return True

        monkeypatch.setattr(user_dao, "update_token", fake_update_token)
        code, msg = self.user_model.logout(self.user_id, token)
        assert (code, msg) == (200, "ok")
        assert called["user_id"] == self.user_id

    def test_register_new_user_success(self):
        new_user_model = User()
        unique_id = f"user_new_{uuid.uuid4()}"
        code, msg = new_user_model.register(unique_id, "pwd")
        assert (code, msg) == (200, "ok")

    def test_check_token_success(self):
        code, msg, token = self.user_model.login(
            self.user_id, self.password, terminal="term"
        )
        assert code == 200
        assert self.user_model.check_token(self.user_id, token) == (200, "ok")
