import json
import uuid

from be.model.mongo import get_book_collection
from be.model.seller import Seller
from be.model.user import User


class TestSellerErrorBranches:
    def setup_method(self):
        self.collection = get_book_collection()
        self.user = User()
        self.seller = Seller()
        uid = uuid.uuid4().hex
        self.seller_id = f"seller-errors-{uid}"
        self.store_id = f"seller-errors-store-{uid}"
        self.book_id = f"seller-errors-book-{uid}"
        self.password = "pwd"
        assert self.user.register(self.seller_id, self.password)[0] == 200

    def teardown_method(self):
        self.collection.delete_many({"doc_type": "inventory", "store_id": self.store_id})
        self.collection.delete_many({"doc_type": "store", "store_id": self.store_id})
        self.collection.delete_many({"doc_type": "user", "user_id": self.seller_id})

    def test_add_book_user_not_exist(self):
        book_json = json.dumps({"title": "invalid", "price": 10})
        code, _ = self.seller.add_book("ghost-user", self.store_id, self.book_id, book_json, 5)
        assert code == 511

    def test_add_book_store_not_exist(self):
        book_json = json.dumps({"title": "missing store", "price": 10})
        code, _ = self.seller.add_book(self.seller_id, "ghost-store", self.book_id, book_json, 5)
        assert code == 513

    def test_add_book_duplicate(self):
        book_json = json.dumps({"title": "dup", "price": 10})
        assert self.seller.create_store(self.seller_id, self.store_id)[0] == 200
        assert (
            self.seller.add_book(self.seller_id, self.store_id, self.book_id, book_json, 5)[0]
            == 200
        )
        code, _ = self.seller.add_book(
            self.seller_id, self.store_id, self.book_id, book_json, 1
        )
        assert code == 516

    def test_add_stock_level_missing_book(self):
        assert self.seller.create_store(self.seller_id, self.store_id)[0] == 200
        code, _ = self.seller.add_stock_level(
            self.seller_id, self.store_id, "ghost-book", 5
        )
        assert code == 515

    def test_add_stock_level_wrong_user(self):
        assert self.seller.create_store(self.seller_id, self.store_id)[0] == 200
        book_json = json.dumps({"title": "stock", "price": 10})
        self.seller.add_book(self.seller_id, self.store_id, self.book_id, book_json, 1)
        code, _ = self.seller.add_stock_level(
            "ghost-user", self.store_id, self.book_id, 3
        )
        assert code == 511

    def test_create_store_duplicate(self):
        assert self.seller.create_store(self.seller_id, self.store_id)[0] == 200
        code, _ = self.seller.create_store(self.seller_id, self.store_id)
        assert code == 514
