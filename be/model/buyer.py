import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from pymongo.errors import PyMongoError

from be.model import db_conn
from be.model import error


class Buyer(db_conn.DBConn):
    pending_timeout = 1800

    def __init__(self):
        super().__init__()
        self.pending_timeout = getattr(self, "pending_timeout", 1800)


    def __restore_inventory(self, store_id: str, items: List[Dict]):
        for item in items:
            book_id = item.get("book_id")
            count = int(item.get("count", 0))
            if not book_id or count <= 0:
                continue
            self.collection.update_one(
                {
                    "doc_type": "inventory",
                    "store_id": store_id,
                    "book_id": book_id,
                },
                {
                    "$inc": {"stock_level": count},
                    "$set": {"updated_at": datetime.utcnow()},
                },
            )

    def cancel_expired_orders(self) -> int:
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self.pending_timeout)
        expired = list(
            self.collection.find(
                {
                    "doc_type": "order",
                    "status": "pending",
                    "$or": [
                        {"expires_at": {"$lte": now}},
                        {
                            "expires_at": {"$exists": False},
                            "created_at": {"$lt": cutoff},
                        },
                    ],
                },
                {
                    "_id": 0,
                    "order_id": 1,
                    "store_id": 1,
                    "items": 1,
                },
            )
        )
        cancelled = 0
        for order in expired:
            order_id = order.get("order_id")
            store_id = order.get("store_id")
            if not order_id or not store_id:
                continue
            self.__restore_inventory(store_id, order.get("items", []))
            result = self.collection.update_one(
                {
                    "doc_type": "order",
                    "order_id": order_id,
                    "status": "pending",
                },
                {
                    "$set": {
                        "status": "cancelled_timeout",
                        "cancelled_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                        "expires_at": order.get("expires_at"),
                    }
                },
            )
            if result.modified_count:
                cancelled += 1
        return cancelled
    def new_order(
        self, user_id: str, store_id: str, id_and_count: List[Tuple[str, int]]
    ) -> Tuple[int, str, str]:
        order_id = ""
        try:
            if not self.user_id_exist(user_id):
                return error.error_non_exist_user_id(user_id) + (order_id,)
            if not self.store_id_exist(store_id):
                return error.error_non_exist_store_id(store_id) + (order_id,)

            order_id = f"{user_id}_{store_id}_{uuid.uuid1()}"
            order_items = []
            for book_id, count in id_and_count:
                inventory = self.collection.find_one(
                    {
                        "doc_type": "inventory",
                        "store_id": store_id,
                        "book_id": book_id,
                    },
                    {"book_info": 1, "stock_level": 1, "_id": 0},
                )
                if inventory is None:
                    return error.error_non_exist_book_id(book_id) + (order_id,)
                stock_level = inventory.get("stock_level", 0)
                if stock_level < count:
                    return error.error_stock_level_low(book_id) + (order_id,)
                book_info = inventory.get("book_info", "{}")
                book_info_json = json.loads(book_info)
                price = book_info_json.get("price")
                order_items.append(
                    {"book_id": book_id, "count": count, "price": price}
                )

            updated_inventory = []
            for item in order_items:
                result = self.collection.update_one(
                    {
                        "doc_type": "inventory",
                        "store_id": store_id,
                        "book_id": item["book_id"],
                        "stock_level": {"$gte": item["count"]},
                    },
                    {
                        "$inc": {"stock_level": -item["count"]},
                        "$set": {"updated_at": datetime.utcnow()},
                    },
                )
                if result.modified_count == 0:
                    self.__rollback_inventory(store_id, updated_inventory)
                    return error.error_stock_level_low(item["book_id"]) + (order_id,)
                updated_inventory.append((item["book_id"], item["count"]))

            now = datetime.utcnow()
            expires_at = now + timedelta(seconds=self.pending_timeout)
            order_doc = {
                "doc_type": "order",
                "order_id": order_id,
                "user_id": user_id,
                "store_id": store_id,
                "items": order_items,
                "created_at": now,
                "updated_at": now,
                "status": "pending",
                "payment_time": None,
                "shipment_time": None,
                "delivery_time": None,
                "expires_at": expires_at,
            }
            self.collection.insert_one(order_doc)
            return 200, "ok", order_id
        except PyMongoError as e:
            logging.info("528, %s", str(e))
            return 528, "{}".format(str(e)), ""
        except BaseException as e:
            logging.info("530, %s", str(e))
            return 530, "{}".format(str(e)), ""

    def payment(self, user_id: str, password: str, order_id: str) -> Tuple[int, str]:
        try:
            self.cancel_expired_orders()
            order = self.collection.find_one(
                {"doc_type": "order", "order_id": order_id},
                {"_id": 0},
            )
            if order is None:
                return error.error_invalid_order_id(order_id)
            buyer_id = order.get("user_id")
            store_id = order.get("store_id")
            if buyer_id != user_id:
                return error.error_authorization_fail()
            if order.get("status") != "pending":
                return error.error_invalid_order_status(order_id)

            buyer_doc = self.collection.find_one(
                {"doc_type": "user", "user_id": buyer_id},
                {"password": 1, "balance": 1, "_id": 0},
            )
            if buyer_doc is None:
                return error.error_non_exist_user_id(buyer_id)
            if buyer_doc.get("password") != password:
                return error.error_authorization_fail()

            store_doc = self.collection.find_one(
                {"doc_type": "store", "store_id": store_id},
                {"user_id": 1, "_id": 0},
            )
            if store_doc is None:
                return error.error_non_exist_store_id(store_id)
            seller_id = store_doc.get("user_id")
            if not self.user_id_exist(seller_id):
                return error.error_non_exist_user_id(seller_id)

            total_price = 0
            for item in order.get("items", []):
                count = item.get("count", 0)
                price = item.get("price", 0)
                total_price = total_price + price * count

            result = self.collection.update_one(
                {
                    "doc_type": "user",
                    "user_id": buyer_id,
                    "balance": {"$gte": total_price},
                },
                {
                    "$inc": {"balance": -total_price},
                    "$set": {"updated_at": datetime.utcnow()},
                },
            )
            if result.modified_count == 0:
                return error.error_not_sufficient_funds(order_id)

            result = self.collection.update_one(
                {"doc_type": "user", "user_id": seller_id},
                {
                    "$inc": {"balance": total_price},
                    "$set": {"updated_at": datetime.utcnow()},
                },
            )
            if result.modified_count == 0:
                return error.error_non_exist_user_id(seller_id)

            update_order = self.collection.update_one(
                {
                    "doc_type": "order",
                    "order_id": order_id,
                    "status": "pending",
                },
                {
                    "$set": {
                        "status": "paid",
                        "payment_time": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            if update_order.modified_count == 0:
                return error.error_invalid_order_status(order_id)

            return 200, "ok"
        except PyMongoError as e:
            return 528, "{}".format(str(e))
        except BaseException as e:
            return 530, "{}".format(str(e))

    def add_funds(self, user_id, password, add_value) -> Tuple[int, str]:
        try:
            user_doc = self.collection.find_one(
                {"doc_type": "user", "user_id": user_id},
                {"password": 1, "_id": 0},
            )
            if user_doc is None:
                return error.error_authorization_fail()
            if user_doc.get("password") != password:
                return error.error_authorization_fail()

            result = self.collection.update_one(
                {"doc_type": "user", "user_id": user_id},
                {
                    "$inc": {"balance": int(add_value)},
                    "$set": {"updated_at": datetime.utcnow()},
                },
            )
            if result.matched_count == 0:
                return error.error_non_exist_user_id(user_id)

            return 200, "ok"
        except PyMongoError as e:
            return 528, "{}".format(str(e))
        except BaseException as e:
            return 530, "{}".format(str(e))

    def confirm_receipt(self, user_id: str, order_id: str) -> Tuple[int, str]:
        try:
            order = self.collection.find_one(
                {"doc_type": "order", "order_id": order_id},
                {"user_id": 1, "status": 1, "_id": 0},
            )
            if order is None:
                return error.error_invalid_order_id(order_id)
            if order.get("user_id") != user_id:
                return error.error_authorization_fail()
            if order.get("status") != "shipped":
                return error.error_invalid_order_status(order_id)

            result = self.collection.update_one(
                {
                    "doc_type": "order",
                    "order_id": order_id,
                    "status": "shipped",
                },
                {
                    "$set": {
                        "status": "delivered",
                        "delivery_time": datetime.utcnow(),
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

    def cancel_order(
        self, user_id: str, password: Optional[str], order_id: str
    ) -> Tuple[int, str]:
        try:
            self.cancel_expired_orders()
            order = self.collection.find_one(
                {"doc_type": "order", "order_id": order_id},
                {"_id": 0},
            )
            if order is None:
                return error.error_invalid_order_id(order_id)
            if order.get("user_id") != user_id:
                return error.error_authorization_fail()
            if order.get("status") != "pending":
                return error.error_invalid_order_status(order_id)
            if password is not None:
                user_doc = self.collection.find_one(
                    {"doc_type": "user", "user_id": user_id},
                    {"password": 1, "_id": 0},
                )
                if user_doc is None or user_doc.get("password") != password:
                    return error.error_authorization_fail()

            self.__restore_inventory(order.get("store_id"), order.get("items", []))
            result = self.collection.update_one(
                {
                    "doc_type": "order",
                    "order_id": order_id,
                    "status": "pending",
                },
                {
                    "$set": {
                        "status": "cancelled",
                        "cancelled_at": datetime.utcnow(),
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

    def list_orders(
        self,
        user_id: str,
        status: Optional[str],
        page: int,
        page_size: int,
    ) -> Tuple[int, str, Dict]:
        try:
            self.cancel_expired_orders()
            if not self.user_id_exist(user_id):
                return error.error_non_exist_user_id(user_id) + ({},)
            safe_page = max(page or 1, 1)
            safe_page_size = max(min(page_size or 20, 50), 1)
            query: Dict = {"doc_type": "order", "user_id": user_id}
            if status:
                query["status"] = status
            cursor = (
                self.collection.find(
                    query,
                    {"_id": 0},
                )
                .sort([("updated_at", -1)])
                .skip((safe_page - 1) * safe_page_size)
                .limit(safe_page_size)
            )
            orders = []
            for doc in cursor:
                orders.append(doc)
            total = self.collection.count_documents(query)
            payload = {
                "page": safe_page,
                "page_size": safe_page_size,
                "total": total,
                "orders": orders,
            }
            return 200, "ok", payload
        except PyMongoError as e:
            return 528, "{}".format(str(e)), {}
        except BaseException as e:
            return 530, "{}".format(str(e)), {}
