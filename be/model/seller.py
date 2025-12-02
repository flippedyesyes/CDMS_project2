import json
from datetime import datetime
from typing import Dict

from pymongo.errors import DuplicateKeyError, PyMongoError

from be.model import error
from be.model import db_conn


class Seller(db_conn.DBConn):
    def __init__(self):
        super().__init__()

    def add_book(
        self,
        user_id: str,
        store_id: str,
        book_id: str,
        book_json_str: str,
        stock_level: int,
    ):
        try:
            if not self.user_id_exist(user_id):
                return error.error_non_exist_user_id(user_id)
            if not self.store_id_exist(store_id):
                return error.error_non_exist_store_id(store_id)
            if self.book_id_exist(store_id, book_id):
                return error.error_exist_book_id(book_id)

            search_pieces = []
            text_fields: Dict[str, str] = {}
            try:
                book_obj = json.loads(book_json_str)
            except (TypeError, ValueError):
                book_obj = {}
            if isinstance(book_obj, dict):
                for key in (
                    "title",
                    "sub_title",
                    "author",
                    "publisher",
                    "translator",
                    "book_intro",
                    "author_intro",
                    "content",
                ):
                    value = book_obj.get(key)
                    if isinstance(value, str):
                        search_pieces.append(value)
                        if key in {"title", "book_intro", "content"}:
                            text_fields[key] = value
                tags = book_obj.get("tags")
                if isinstance(tags, list):
                    search_pieces.extend(str(tag) for tag in tags if tag)
                    text_fields["tags"] = tags
                elif isinstance(tags, str):
                    search_pieces.append(tags)
                    text_fields["tags"] = tags
                catalog = book_obj.get("catalog")
                if isinstance(catalog, str):
                    search_pieces.append(catalog)
            search_text = " ".join(piece for piece in search_pieces if piece)

            doc = {
                "doc_type": "inventory",
                "store_id": store_id,
                "book_id": book_id,
                "book_info": book_json_str,
                "stock_level": int(stock_level),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "search_text": search_text,
            }
            doc.update(text_fields)
            self.collection.insert_one(doc)
            return 200, "ok"
        except DuplicateKeyError:
            return error.error_exist_book_id(book_id)
        except PyMongoError as e:
            return 528, "{}".format(str(e))
        except BaseException as e:
            return 530, "{}".format(str(e))

    def add_stock_level(
        self, user_id: str, store_id: str, book_id: str, add_stock_level: int
    ):
        try:
            if not self.user_id_exist(user_id):
                return error.error_non_exist_user_id(user_id)
            if not self.store_id_exist(store_id):
                return error.error_non_exist_store_id(store_id)
            if not self.book_id_exist(store_id, book_id):
                return error.error_non_exist_book_id(book_id)

            result = self.collection.update_one(
                {
                    "doc_type": "inventory",
                    "store_id": store_id,
                    "book_id": book_id,
                },
                {
                    "$inc": {"stock_level": int(add_stock_level)},
                    "$set": {"updated_at": datetime.utcnow()},
                },
            )
            if result.matched_count == 0:
                return error.error_non_exist_book_id(book_id)
            return 200, "ok"
        except PyMongoError as e:
            return 528, "{}".format(str(e))
        except BaseException as e:
            return 530, "{}".format(str(e))

    def create_store(self, user_id: str, store_id: str) -> (int, str):
        try:
            if not self.user_id_exist(user_id):
                return error.error_non_exist_user_id(user_id)
            if self.store_id_exist(store_id):
                return error.error_exist_store_id(store_id)

            doc = {
                "doc_type": "store",
                "store_id": store_id,
                "user_id": user_id,
                "created_at": datetime.utcnow(),
            }
            self.collection.insert_one(doc)
            return 200, "ok"
        except DuplicateKeyError:
            return error.error_exist_store_id(store_id)
        except PyMongoError as e:
            return 528, "{}".format(str(e))
        except BaseException as e:
            return 530, "{}".format(str(e))

    def ship_order(self, user_id: str, store_id: str, order_id: str):
        try:
            if not self.user_id_exist(user_id):
                return error.error_non_exist_user_id(user_id)
            store_doc = self.collection.find_one(
                {"doc_type": "store", "store_id": store_id},
                {"user_id": 1, "_id": 0},
            )
            if store_doc is None:
                return error.error_non_exist_store_id(store_id)
            if store_doc.get("user_id") != user_id:
                return error.error_authorization_fail()

            order = self.collection.find_one(
                {"doc_type": "order", "order_id": order_id},
                {"store_id": 1, "status": 1, "_id": 0},
            )
            if order is None:
                return error.error_invalid_order_id(order_id)
            if order.get("store_id") != store_id:
                return error.error_authorization_fail()
            if order.get("status") != "paid":
                return error.error_invalid_order_status(order_id)

            result = self.collection.update_one(
                {
                    "doc_type": "order",
                    "order_id": order_id,
                    "status": "paid",
                },
                {
                    "$set": {
                        "status": "shipped",
                        "shipment_time": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            if result.modified_count == 0:
                return error.error_invalid_order_status(order_id)
            return 200, "ok"
        except PyMongoError as e:
            return 528, "{}".format(str(e))
        except BaseException as e:
            return 530, "{}".format(str(e))
