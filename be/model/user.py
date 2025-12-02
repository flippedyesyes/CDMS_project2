import logging
import time
from datetime import datetime
from typing import Dict, Tuple

import jwt
from jwt import exceptions as jwt_exceptions
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError

from be.model import error
from be.model.mongo import get_book_collection


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


class User:
    token_lifetime: int = 3600
    _doc_type = "user"

    def __init__(self):
        self.collection: Collection = get_book_collection()

    def __user_filter(self, user_id: str) -> Dict:
        return {"doc_type": self._doc_type, "user_id": user_id}

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
        doc = {
            "doc_type": self._doc_type,
            "user_id": user_id,
            "password": password,
            "balance": 0,
            "token": token,
            "terminal": terminal,
            "created_at": now,
            "updated_at": now,
        }
        try:
            self.collection.insert_one(doc)
        except DuplicateKeyError:
            return error.error_exist_user_id(user_id)
        except PyMongoError as e:
            logging.error("register mongo error: %s", str(e))
            return 528, "{}".format(str(e))
        except BaseException as e:
            logging.error("register unexpected error: %s", str(e))
            return 530, "{}".format(str(e))
        return 200, "ok"

    def check_token(self, user_id: str, token: str) -> Tuple[int, str]:
        try:
            doc = self.collection.find_one(
                self.__user_filter(user_id), {"token": 1, "_id": 0}
            )
            if doc is None:
                return error.error_authorization_fail()
            if not self.__check_token(user_id, doc.get("token"), token):
                return error.error_authorization_fail()
            return 200, "ok"
        except PyMongoError as e:
            logging.error("check_token mongo error: %s", str(e))
            return 528, "{}".format(str(e))

    def check_password(self, user_id: str, password: str) -> Tuple[int, str]:
        try:
            doc = self.collection.find_one(
                self.__user_filter(user_id), {"password": 1, "_id": 0}
            )
            if doc is None:
                return error.error_authorization_fail()
            if password != doc.get("password"):
                return error.error_authorization_fail()
            return 200, "ok"
        except PyMongoError as e:
            logging.error("check_password mongo error: %s", str(e))
            return 528, "{}".format(str(e))

    def login(self, user_id: str, password: str, terminal: str) -> Tuple[int, str, str]:
        try:
            code, message = self.check_password(user_id, password)
            if code != 200:
                return code, message, ""
            token = jwt_encode(user_id, terminal)
            result = self.collection.update_one(
                self.__user_filter(user_id),
                {
                    "$set": {
                        "token": token,
                        "terminal": terminal,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            if result.matched_count == 0:
                return error.error_authorization_fail() + ("",)
            return 200, "ok", token
        except PyMongoError as e:
            logging.error("login mongo error: %s", str(e))
            return 528, "{}".format(str(e)), ""
        except BaseException as e:
            logging.error("login unexpected error: %s", str(e))
            return 530, "{}".format(str(e)), ""

    def logout(self, user_id: str, token: str) -> Tuple[int, str]:
        try:
            code, message = self.check_token(user_id, token)
            if code != 200:
                return code, message
            terminal = f"terminal_{time.time()}"
            dummy_token = jwt_encode(user_id, terminal)
            result = self.collection.update_one(
                self.__user_filter(user_id),
                {
                    "$set": {
                        "token": dummy_token,
                        "terminal": terminal,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            if result.matched_count == 0:
                return error.error_authorization_fail()
            return 200, "ok"
        except PyMongoError as e:
            logging.error("logout mongo error: %s", str(e))
            return 528, "{}".format(str(e))
        except BaseException as e:
            logging.error("logout unexpected error: %s", str(e))
            return 530, "{}".format(str(e))

    def unregister(self, user_id: str, password: str) -> Tuple[int, str]:
        try:
            code, message = self.check_password(user_id, password)
            if code != 200:
                return code, message
            result = self.collection.delete_one(self.__user_filter(user_id))
            if result.deleted_count != 1:
                return error.error_authorization_fail()
            return 200, "ok"
        except PyMongoError as e:
            logging.error("unregister mongo error: %s", str(e))
            return 528, "{}".format(str(e))
        except BaseException as e:
            logging.error("unregister unexpected error: %s", str(e))
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
            result = self.collection.update_one(
                self.__user_filter(user_id),
                {
                    "$set": {
                        "password": new_password,
                        "token": token,
                        "terminal": terminal,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            if result.matched_count == 0:
                return error.error_authorization_fail()
            return 200, "ok"
        except PyMongoError as e:
            logging.error("change_password mongo error: %s", str(e))
            return 528, "{}".format(str(e))
        except BaseException as e:
            logging.error("change_password unexpected error: %s", str(e))
            return 530, "{}".format(str(e))
