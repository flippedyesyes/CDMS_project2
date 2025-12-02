import uuid

import pytest

from be.model import error
from fe import conf
from fe.access.auth import Auth
from fe.access.new_buyer import register_new_buyer
from fe.access.new_seller import register_new_seller
from fe.test.gen_book_data import GenBook


@pytest.fixture
def order_context():
    seller_id = f"edge_seller_{uuid.uuid1()}"
    store_id = f"edge_store_{uuid.uuid1()}"
    buyer_id = f"edge_buyer_{uuid.uuid1()}"
    password = seller_id

    gen_book = GenBook(seller_id, store_id)
    ok, buy_book_id_list = gen_book.gen(
        non_exist_book_id=False, low_stock_level=False, max_book_count=5
    )
    assert ok

    buyer = register_new_buyer(buyer_id, password)
    code, order_id = buyer.new_order(store_id, buy_book_id_list)
    assert code == 200

    total_price = 0
    for book_info, count in gen_book.buy_book_info_list:
        if book_info.price is None:
            continue
        total_price += book_info.price * count

    return {
        "seller": gen_book.seller,
        "seller_id": seller_id,
        "store_id": store_id,
        "buyer": buyer,
        "order_id": order_id,
        "total_price": total_price,
        "password": password,
    }


def test_payment_fails_when_seller_removed(order_context):
    buyer = order_context["buyer"]
    assert buyer.add_funds(order_context["total_price"]) == 200

    auth_client = Auth(conf.URL)
    assert (
        auth_client.unregister(order_context["seller_id"], order_context["password"])
        == 200
    )

    code = buyer.payment(order_context["order_id"])
    assert code == 511


def test_confirm_receipt_wrong_user(order_context):
    buyer = order_context["buyer"]
    seller = order_context["seller"]
    assert buyer.add_funds(order_context["total_price"]) == 200
    assert buyer.payment(order_context["order_id"]) == 200
    assert seller.ship_order(order_context["store_id"], order_context["order_id"]) == 200

    intruder_id = f"intruder_{uuid.uuid1()}"
    intruder = register_new_buyer(intruder_id, intruder_id)
    assert intruder.confirm_receipt(order_context["order_id"]) == 401


def test_ship_order_wrong_store(order_context):
    buyer = order_context["buyer"]
    seller = order_context["seller"]
    assert buyer.add_funds(order_context["total_price"]) == 200
    assert buyer.payment(order_context["order_id"]) == 200

    wrong_store_id = order_context["store_id"] + "_wrong"
    assert seller.ship_order(wrong_store_id, order_context["order_id"]) == 513


def test_error_invalid_order_status_message():
    code, message = error.error_invalid_order_status("order-123")
    assert code == 520
    assert "order-123" in message


def test_ship_order_wrong_owner(order_context):
    buyer = order_context["buyer"]
    seller = order_context["seller"]
    assert buyer.add_funds(order_context["total_price"]) == 200
    assert buyer.payment(order_context["order_id"]) == 200

    other_seller_id = f"other_seller_{uuid.uuid1()}"
    other_seller = register_new_seller(other_seller_id, other_seller_id)
    assert other_seller.ship_order(
        order_context["store_id"], order_context["order_id"]
    ) == 401


def test_confirm_receipt_invalid_order(order_context):
    buyer = order_context["buyer"]
    assert buyer.confirm_receipt("non_exist_order") == 518
