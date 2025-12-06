import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from be.model import db_conn
from be.model import error
from be.model.dao import user_dao, store_dao, order_dao


class Buyer(db_conn.DBConn):
    pending_timeout = 1800

    def __init__(self):
        super().__init__()
        self.pending_timeout = getattr(self, "pending_timeout", 1800)

    def __restore_inventory(self, session, store_id: str, items: List[Tuple[str, int]]):
        if not items:
            return
        order_dao.adjust_inventory_for_items(
            session, store_id, items, decrease=False
        )

    def cancel_expired_orders(self) -> int:
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self.pending_timeout)
        with self.session_scope() as session:
            expired_orders = order_dao.find_expired_pending_orders(
                session, now, cutoff
            )
            cancelled = 0
            for order in expired_orders:
                items = order_dao.get_order_items(session, order.order_id)
                tuples = [(item.book_id, item.count) for item in items]
                self.__restore_inventory(session, order.store_id, tuples)
                order_dao.update_order_status(
                    session,
                    order_id=order.order_id,
                    expected_status="pending",
                    new_status="cancelled_timeout",
                    cancelled_at=now,
                    updated_at=now,
                )
                cancelled += 1
            return cancelled

    def new_order(
        self, user_id: str, store_id: str, id_and_count: List[Tuple[str, int]]
    ) -> Tuple[int, str, str]:
        order_id = ""
        try:
            with self.session_scope() as session:
                buyer = user_dao.get_user(session, user_id)
                if buyer is None:
                    return error.error_non_exist_user_id(user_id) + (order_id,)
                store = store_dao.get_store(session, store_id)
                if store is None:
                    return error.error_non_exist_store_id(store_id) + (order_id,)
                order_id = f"{user_id}_{store_id}_{uuid.uuid1()}"

                order_items = []
                stock_tuples = []
                for book_id, count in id_and_count:
                    inventory = store_dao.get_inventory(session, store_id, book_id)
                    if inventory is None:
                        return error.error_non_exist_book_id(book_id) + (order_id,)
                    if inventory.stock_level < count:
                        return error.error_stock_level_low(book_id) + (order_id,)
                    price = inventory.price
                    if price is None:
                        try:
                            info = json.loads(inventory.book_info or "{}")
                        except (TypeError, ValueError):
                            info = {}
                        price = info.get("price", 0)
                    order_items.append((book_id, count, int(price or 0)))
                    stock_tuples.append((book_id, count))

                if not order_dao.adjust_inventory_for_items(
                    session, store_id, stock_tuples, decrease=True
                ):
                    return error.error_stock_level_low(stock_tuples[0][0]) + (order_id,)

                total_price = sum(price * count for _, count, price in order_items)
                now = datetime.utcnow()
                expires_at = now + timedelta(seconds=self.pending_timeout)
                order_dao.create_order(
                    session,
                    order_id=order_id,
                    user_id=user_id,
                    store_id=store_id,
                    status="pending",
                    total_price=total_price,
                    expires_at=expires_at,
                )
                order_dao.add_order_items(session, order_id, order_items)
            return 200, "ok", order_id
        except BaseException as e:
            logging.exception("new_order failed: %s", e)
            return 530, "{}".format(str(e)), ""

    def payment(self, user_id: str, password: str, order_id: str) -> Tuple[int, str]:
        try:
            self.cancel_expired_orders()
            with self.session_scope() as session:
                order = order_dao.get_order(session, order_id)
                if order is None:
                    return error.error_invalid_order_id(order_id)
                if order.user_id != user_id:
                    return error.error_authorization_fail()
                if order.status != "pending":
                    return error.error_invalid_order_status(order_id)

                buyer = user_dao.get_user(session, user_id)
                if buyer is None:
                    return error.error_non_exist_user_id(user_id)
                if buyer.password != password:
                    return error.error_authorization_fail()

                store = store_dao.get_store(session, order.store_id)
                if store is None:
                    return error.error_non_exist_store_id(order.store_id)
                seller_id = store.owner_id
                if user_dao.get_user(session, seller_id) is None:
                    return error.error_non_exist_user_id(seller_id)

                total_price = order.total_price
                if not user_dao.change_balance(session, user_id, -total_price):
                    return error.error_not_sufficient_funds(order_id)
                if not user_dao.change_balance(session, seller_id, total_price):
                    return error.error_non_exist_user_id(seller_id)

                updated = order_dao.update_order_status(
                    session,
                    order_id=order_id,
                    expected_status="pending",
                    new_status="paid",
                    payment_time=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                if not updated:
                    return error.error_invalid_order_status(order_id)
            return 200, "ok"
        except BaseException as e:
            return 530, "{}".format(str(e))

    def add_funds(self, user_id, password, add_value) -> Tuple[int, str]:
        try:
            with self.session_scope() as session:
                user = user_dao.get_user(session, user_id)
                if user is None or user.password != password:
                    return error.error_authorization_fail()
                if not user_dao.change_balance(session, user_id, int(add_value)):
                    return error.error_non_exist_user_id(user_id)
            return 200, "ok"
        except BaseException as e:
            return 530, "{}".format(str(e))

    def confirm_receipt(self, user_id: str, order_id: str) -> Tuple[int, str]:
        try:
            with self.session_scope() as session:
                order = order_dao.get_order(session, order_id)
                if order is None:
                    return error.error_invalid_order_id(order_id)
                if order.user_id != user_id:
                    return error.error_authorization_fail()
                if order.status != "shipped":
                    return error.error_invalid_order_status(order_id)
                updated = order_dao.update_order_status(
                    session,
                    order_id=order_id,
                    expected_status="shipped",
                    new_status="delivered",
                    delivery_time=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                if not updated:
                    return error.error_invalid_order_status(order_id)
            return 200, "ok"
        except BaseException as e:
            return 530, "{}".format(str(e))

    def cancel_order(
        self, user_id: str, password: Optional[str], order_id: str
    ) -> Tuple[int, str]:
        try:
            self.cancel_expired_orders()
            with self.session_scope() as session:
                order = order_dao.get_order(session, order_id)
                if order is None:
                    return error.error_invalid_order_id(order_id)
                if order.user_id != user_id:
                    return error.error_authorization_fail()
                if order.status != "pending":
                    return error.error_invalid_order_status(order_id)
                if password is not None:
                    user = user_dao.get_user(session, user_id)
                    if user is None or user.password != password:
                        return error.error_authorization_fail()

                items = order_dao.get_order_items(session, order_id)
                tuples = [(item.book_id, item.count) for item in items]
                self.__restore_inventory(session, order.store_id, tuples)
                updated = order_dao.update_order_status(
                    session,
                    order_id=order_id,
                    expected_status="pending",
                    new_status="cancelled",
                    cancelled_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                if not updated:
                    return error.error_invalid_order_status(order_id)
            return 200, "ok"
        except BaseException as e:
            return 530, "{}".format(str(e))

    def __serialize_order(self, order, items):
        def _ts(value):
            return value.isoformat() if value else None

        return {
            "order_id": order.order_id,
            "user_id": order.user_id,
            "store_id": order.store_id,
            "status": order.status,
            "total_price": order.total_price,
            "created_at": _ts(order.created_at),
            "updated_at": _ts(order.updated_at),
            "payment_time": _ts(order.payment_time),
            "shipment_time": _ts(order.shipment_time),
            "delivery_time": _ts(order.delivery_time),
            "expires_at": _ts(order.expires_at),
            "items": [
                {
                    "book_id": item.book_id,
                    "count": item.count,
                    "price": item.unit_price,
                }
                for item in items
            ],
        }

    def list_orders(
        self,
        user_id: str,
        status: Optional[str],
        page: int,
        page_size: int,
    ) -> Tuple[int, str, Dict]:
        try:
            self.cancel_expired_orders()
            with self.session_scope() as session:
                if user_dao.get_user(session, user_id) is None:
                    return error.error_non_exist_user_id(user_id) + ({},)
                safe_page = max(page or 1, 1)
                safe_page_size = max(min(page_size or 20, 50), 1)
                total, orders = order_dao.list_orders(
                    session,
                    user_id=user_id,
                    status=status,
                    created_from=None,
                    created_to=None,
                    sort_by="updated_at",
                    page=safe_page,
                    page_size=safe_page_size,
                )
                serialized = []
                for order in orders:
                    items = order_dao.get_order_items(session, order.order_id)
                    serialized.append(self.__serialize_order(order, items))
                payload = {
                    "page": safe_page,
                    "page_size": safe_page_size,
                    "total": total,
                    "orders": serialized,
                }
                return 200, "ok", payload
        except BaseException as e:
            return 530, "{}".format(str(e)), {}
