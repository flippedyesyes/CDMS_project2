import uuid

import pytest

from fe import conf
from fe.access import book
from fe.access.new_buyer import register_new_buyer
from fe.access.new_seller import register_new_seller


class TestBuyerExport:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.seller_id = f"seller_export_{uuid.uuid4()}"
        self.store_id = f"store_export_{uuid.uuid4()}"
        self.password = self.seller_id
        self.seller = register_new_seller(self.seller_id, self.password)
        assert self.seller.create_store(self.store_id) == 200

        book_db = book.BookDB(conf.Use_Large_DB)
        self.book = book_db.get_book_info(0, 1)[0]
        assert self.seller.add_book(self.store_id, 10, self.book) == 200

        self.buyer_id = f"buyer_export_{uuid.uuid4()}"
        self.buyer = register_new_buyer(self.buyer_id, self.password)
        # preload balance to simplify tests
        assert self.buyer.add_funds(100000) == 200
        yield

    def _create_order(self, pay=False):
        code, order_id = self.buyer.new_order(self.store_id, [(self.book.id, 1)])
        assert code == 200
        if pay:
            assert self.buyer.payment(order_id) == 200
        return order_id

    def test_export_orders_json(self):
        paid_order = self._create_order(pay=True)
        self._create_order(pay=False)

        status, data = self.buyer.export_orders(status="paid")
        assert status == 200
        orders = data.get("orders", [])
        assert any(o["order_id"] == paid_order for o in orders)
        assert all(o["status"] == "paid" for o in orders)

    def test_export_orders_csv(self):
        order_id = self._create_order(pay=True)
        status, csv_text = self.buyer.export_orders(fmt="csv")
        assert status == 200
        assert "order_id" in csv_text
        assert order_id in csv_text
