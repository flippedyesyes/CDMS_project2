import logging
import time
from datetime import datetime
from typing import Dict, Tuple

import jwt
from jwt import exceptions as jwt_exceptions

from be.model import error
from be.model.db_conn import DBConn
from be.model.dao import user_dao


def jwt_encode(user_id: str, terminal: str) -> str:
    encoded = jwt.encode(
        {"user_id": user_id, "terminal": terminal, "timestamp": time.time()},
        key=user_id,
        algorithm="HS256",
    )
    if isinstance(encoded, bytes):
        return encoded.decode("utf-8")
    return encoded


def jwt_decode(encoded_token: str, user_id: str) -> Dict:
    return jwt.decode(encoded_token, key=user_id, algorithms=["HS256"])


class User(DBConn):
    token_lifetime: int = 3600
    _doc_type = "user"

    def __check_token(self, user_id: str, db_token: str, token: str) -> bool:
        try:
            if db_token != token:
                return False
            jwt_text = jwt_decode(encoded_token=token, user_id=user_id)
            ts = jwt_text.get("timestamp")
            if ts is None:
                return False
            now = time.time()
            return 0 <= now - ts < self.token_lifetime
        except jwt_exceptions.PyJWTError as e:
            logging.error("token decode error: %s", str(e))
            return False

    def register(self, user_id: str, password: str):
        now = datetime.utcnow()
        terminal = f"terminal_{time.time()}"
        token = jwt_encode(user_id, terminal)
        try:
            with self.session_scope() as session:
                existing = user_dao.get_user(
                    session, user_id, include_inactive=True
                )
                if existing and existing.status == "active":
                    return error.error_exist_user_id(user_id)
                if existing:
                    user_dao.revive_user(
                        session,
                        existing,
                        password=password,
                        token=token,
                        terminal=terminal,
                    )
                else:
                    user_dao.create_user(
                        session,
                        user_id=user_id,
                        password=password,
                        token=token,
                        terminal=terminal,
                    )
        except BaseException as e:
            logging.error("register error: %s", str(e))
            return 530, "{}".format(str(e))
        return 200, "ok"

    def check_token(self, user_id: str, token: str) -> Tuple[int, str]:
        try:
            with self.session_scope() as session:
                user = user_dao.get_user(session, user_id)
                if user is None:
                    return error.error_authorization_fail()
                if not self.__check_token(user_id, user.token, token):
                    return error.error_authorization_fail()
                return 200, "ok"
        except BaseException as e:
            logging.error("check_token error: %s", str(e))
            return 530, "{}".format(str(e))

    def check_password(self, user_id: str, password: str) -> Tuple[int, str]:
        try:
            with self.session_scope() as session:
                user = user_dao.get_user(session, user_id)
                if user is None or password != user.password:
                    return error.error_authorization_fail()
                return 200, "ok"
        except BaseException as e:
            logging.error("check_password error: %s", str(e))
            return 530, "{}".format(str(e))

    def login(self, user_id: str, password: str, terminal: str) -> Tuple[int, str, str]:
        try:
            code, message = self.check_password(user_id, password)
            if code != 200:
                return code, message, ""
            token = jwt_encode(user_id, terminal)
            with self.session_scope() as session:
                updated = user_dao.update_token(session, user_id, token, terminal)
                if not updated:
                    return error.error_authorization_fail() + ("",)
            return 200, "ok", token
        except BaseException as e:
            logging.error("login error: %s", str(e))
            return 530, "{}".format(str(e)), ""

    def logout(self, user_id: str, token: str) -> Tuple[int, str]:
        try:
            code, message = self.check_token(user_id, token)
            if code != 200:
                return code, message
            terminal = f"terminal_{time.time()}"
            dummy_token = jwt_encode(user_id, terminal)
            with self.session_scope() as session:
                updated = user_dao.update_token(session, user_id, dummy_token, terminal)
                if not updated:
                    return error.error_authorization_fail()
            return 200, "ok"
        except BaseException as e:
            logging.error("logout error: %s", str(e))
            return 530, "{}".format(str(e))

    def unregister(self, user_id: str, password: str) -> Tuple[int, str]:
        try:
            code, message = self.check_password(user_id, password)
            if code != 200:
                return code, message
            with self.session_scope() as session:
                deleted = user_dao.soft_delete_user(session, user_id)
                if not deleted:
                    return error.error_authorization_fail()
            return 200, "ok"
        except BaseException as e:
            logging.error("unregister error: %s", str(e))
            return 530, "{}".format(str(e))

    def change_password(
        self, user_id: str, old_password: str, new_password: str
    ) -> Tuple[int, str]:
        try:
            code, message = self.check_password(user_id, old_password)
            if code != 200:
                return code, message
            terminal = f"terminal_{time.time()}"
            token = jwt_encode(user_id, terminal)
            with self.session_scope() as session:
                updated = user_dao.update_password(
                    session, user_id, new_password, token, terminal
                )
                if not updated:
                    return error.error_authorization_fail()
            return 200, "ok"
        except BaseException as e:
            logging.error("change_password error: %s", str(e))
            return 530, "{}".format(str(e))
