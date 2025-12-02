import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pymongo.errors import PyMongoError

from be.model.user import User


class TestUserModelErrorPaths:
    @pytest.fixture(autouse=True)
    def setup_user(self):
        self.model = User()
        self.user_id = f"user-error-{uuid.uuid4()}"
        self.password = "error-pass"
        yield
        self.model.collection.delete_many(
            {"doc_type": "user", "user_id": {"$regex": "^user-error-"}}
        )

    def test_register_handles_pymongo_error(self):
        with patch.object(
            self.model.collection, "insert_one", side_effect=PyMongoError("db down")
        ):
            code, message = self.model.register(self.user_id, self.password)
        assert code == 528
        assert "db down" in message

    def test_check_token_handles_pymongo_error(self):
        with patch.object(
            self.model.collection, "find_one", side_effect=PyMongoError("fail find")
        ):
            code, message = self.model.check_token(self.user_id, "token")
        assert code == 528
        assert "fail find" in message

    def test_check_password_handles_pymongo_error(self):
        with patch.object(
            self.model.collection, "find_one", side_effect=PyMongoError("fail pwd")
        ):
            code, message = self.model.check_password(self.user_id, self.password)
        assert code == 528
        assert "fail pwd" in message

    def test_login_update_failure_returns_authorization_fail(self):
        assert self.model.register(self.user_id, self.password)[0] == 200
        with patch.object(
            self.model.collection,
            "update_one",
            return_value=SimpleNamespace(matched_count=0),
        ):
            code, message, token = self.model.login(
                self.user_id, self.password, "terminal-login"
            )
        assert code == 401
        assert token == ""

    def test_login_handles_pymongo_error(self):
        assert self.model.register(self.user_id, self.password)[0] == 200
        with patch.object(
            self.model.collection, "update_one", side_effect=PyMongoError("login fail")
        ):
            code, message, token = self.model.login(
                self.user_id, self.password, "terminal-login"
            )
        assert code == 528
        assert token == ""
        assert "login fail" in message

    def test_logout_update_failure_returns_authorization_fail(self):
        assert self.model.register(self.user_id, self.password)[0] == 200
        _, _, token = self.model.login(self.user_id, self.password, "terminal")
        with patch.object(
            self.model.collection,
            "update_one",
            return_value=SimpleNamespace(matched_count=0),
        ):
            code, message = self.model.logout(self.user_id, token)
        assert code == 401

    def test_logout_handles_pymongo_error(self):
        assert self.model.register(self.user_id, self.password)[0] == 200
        _, _, token = self.model.login(self.user_id, self.password, "terminal")
        with patch.object(
            self.model.collection, "update_one", side_effect=PyMongoError("logout fail")
        ):
            code, message = self.model.logout(self.user_id, token)
        assert code == 528
        assert "logout fail" in message

    def test_change_password_update_failure_returns_authorization_fail(self):
        assert self.model.register(self.user_id, self.password)[0] == 200
        with patch.object(
            self.model.collection,
            "update_one",
            return_value=SimpleNamespace(matched_count=0),
        ):
            code, message = self.model.change_password(
                self.user_id, self.password, "next-pass"
            )
        assert code == 401

    def test_change_password_handles_pymongo_error(self):
        assert self.model.register(self.user_id, self.password)[0] == 200
        with patch.object(
            self.model.collection,
            "update_one",
            side_effect=PyMongoError("change fail"),
        ):
            code, message = self.model.change_password(
                self.user_id, self.password, "next-pass"
            )
        assert code == 528
        assert "change fail" in message

    def test_unregister_delete_failure_returns_authorization_fail(self):
        assert self.model.register(self.user_id, self.password)[0] == 200
        with patch.object(
            self.model.collection,
            "delete_one",
            return_value=SimpleNamespace(deleted_count=0),
        ):
            code, message = self.model.unregister(self.user_id, self.password)
        assert code == 401

    def test_unregister_handles_pymongo_error(self):
        assert self.model.register(self.user_id, self.password)[0] == 200
        with patch.object(
            self.model.collection, "delete_one", side_effect=PyMongoError("drop fail")
        ):
            code, message = self.model.unregister(self.user_id, self.password)
        assert code == 528
        assert "drop fail" in message
