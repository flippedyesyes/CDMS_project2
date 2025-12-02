import uuid

from fe.access.auth import Auth
from fe import conf


class TestUserEdgeCases:
    def setup_method(self):
        self.user_id = f"user_edge_{uuid.uuid1()}"
        self.password = "initial_password"
        self.auth = Auth(conf.URL)
        assert self.auth.register(self.user_id, self.password) == 200
        code, token = self.auth.login(self.user_id, self.password, "edge-terminal")
        assert code == 200
        self.token = token

    def teardown_method(self):
        # best-effort cleanup: try to log out and unregister with current credentials
        self.auth.logout(self.user_id, self.token)
        self.auth.unregister(self.user_id, self.password)

    def test_logout_with_invalid_token(self):
        invalid_token = self.token + "tamper"
        assert self.auth.logout(self.user_id, invalid_token) == 401

    def test_change_password_with_wrong_old(self):
        assert (
            self.auth.password(self.user_id, self.password + "_wrong", "new_pass") == 401
        )

    def test_unregister_with_wrong_password(self):
        assert self.auth.unregister(self.user_id, self.password + "_wrong") == 401
