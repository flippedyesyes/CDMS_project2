import pytest
import uuid

from fe.access.new_buyer import register_new_buyer
from fe.test.gen_book_data import GenBook


class TestOrderShippingFlow:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.seller_id = f"test_ship_seller_{uuid.uuid1()}"
        self.store_id = f"test_ship_store_{uuid.uuid1()}"
        self.buyer_id = f"test_ship_buyer_{uuid.uuid1()}"
        self.password = self.seller_id

        self.gen_book = GenBook(self.seller_id, self.store_id)
        ok, buy_book_id_list = self.gen_book.gen(
            non_exist_book_id=False, low_stock_level=False, max_book_count=5
        )
        assert ok

        self.seller = self.gen_book.seller
        self.buyer = register_new_buyer(self.buyer_id, self.password)
        code, self.order_id = self.buyer.new_order(self.store_id, buy_book_id_list)
        assert code == 200

        self.total_price = 0
        for book_info, count in self.gen_book.buy_book_info_list:
            if book_info.price is None:
                continue
            self.total_price += book_info.price * count

        yield

    def _pay_order(self):
        code = self.buyer.add_funds(self.total_price)
        assert code == 200
        code = self.buyer.payment(self.order_id)
        assert code == 200

    def test_ship_and_confirm_success(self):
        self._pay_order()
        assert self.seller.ship_order(self.store_id, self.order_id) == 200
        assert self.buyer.confirm_receipt(self.order_id) == 200

    def test_ship_before_payment(self):
        assert self.seller.ship_order(self.store_id, self.order_id) != 200

    def test_confirm_before_shipping(self):
        self._pay_order()
        assert self.buyer.confirm_receipt(self.order_id) != 200

    def test_confirm_twice(self):
        self._pay_order()
        assert self.seller.ship_order(self.store_id, self.order_id) == 200
        assert self.buyer.confirm_receipt(self.order_id) == 200
        assert self.buyer.confirm_receipt(self.order_id) != 200
