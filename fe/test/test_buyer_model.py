import json
import uuid
from datetime import datetime, timedelta

import pytest

from be.model.buyer import Buyer
from be.model.mongo import get_book_collection
from be.model.seller import Seller
from be.model.user import User


class TestBuyerModelBehaviors:
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        self.collection = get_book_collection()
        self.user = User()
        self.seller = Seller()
        self.buyer = Buyer()

        uid = uuid.uuid4().hex
        self.seller_id = f"buyer-model-seller-{uid}"
        self.buyer_id = f"buyer-model-buyer-{uid}"
        self.store_id = f"buyer-model-store-{uid}"
        self.book_id = f"buyer-model-book-{uid}"
        self.password = "pwd-model"

        assert self.user.register(self.seller_id, self.password)[0] == 200
        assert self.user.register(self.buyer_id, self.password)[0] == 200
        assert self.seller.create_store(self.seller_id, self.store_id)[0] == 200
        book_info = json.dumps({"title": "test", "price": 100})
        assert (
            self.seller.add_book(self.seller_id, self.store_id, self.book_id, book_info, 5)[0]
            == 200
        )
        yield
        self.collection.delete_many({"doc_type": "order", "user_id": self.buyer_id})
        self.collection.delete_many({"doc_type": "inventory", "store_id": self.store_id})
        self.collection.delete_many({"doc_type": "store", "store_id": self.store_id})
        self.collection.delete_many({"doc_type": "user", "user_id": {"$in": [self.buyer_id, self.seller_id]}})

    def _make_order(self):
        code, _, order_id = self.buyer.new_order(
            self.buyer_id, self.store_id, [(self.book_id, 1)]
        )
        assert code == 200
        return order_id

    def test_cancel_order_with_wrong_password(self):
        order_id = self._make_order()
        code, message = self.buyer.cancel_order(self.buyer_id, "wrong", order_id)
        assert code == 401
        assert "authorization" in message.lower()

    def test_cancel_order_status_not_pending(self):
        order_id = self._make_order()
        self.collection.update_one(
            {"doc_type": "order", "order_id": order_id},
            {"$set": {"status": "paid", "updated_at": datetime.utcnow()}},
        )
        code, message = self.buyer.cancel_order(self.buyer_id, self.password, order_id)
        assert code == 520
        assert "invalid order status" in message

    def test_list_orders_status_filter(self):
        order_pending = self._make_order()
        order_cancelled = self._make_order()
        self.collection.update_one(
            {"doc_type": "order", "order_id": order_cancelled},
            {
                "$set": {
                    "status": "cancelled",
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        code, _, payload = self.buyer.list_orders(self.buyer_id, "pending", 1, 10)
        assert code == 200
        ids = {item["order_id"] for item in payload.get("orders", [])}
        assert order_pending in ids
        assert order_cancelled not in ids

    def test_list_orders_non_exist_user(self):
        code, message, payload = self.buyer.list_orders("no-such-user", None, 1, 5)
        assert code == 511
        assert "non exist user" in message
        assert payload == {}
