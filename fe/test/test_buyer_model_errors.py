import contextlib
from types import SimpleNamespace

import pytest

from be.model import buyer as buyer_module, error
from be.model.dao import order_dao, store_dao, user_dao


def dummy_session_scope():
    @contextlib.contextmanager
    def _scope():
        yield SimpleNamespace()

    return _scope


@pytest.fixture
def buyer(monkeypatch):
    b = buyer_module.Buyer()
    b.session_scope = dummy_session_scope()
    b.cancel_expired_orders = lambda: 0
    return b


def test_new_order_store_missing(buyer, monkeypatch):
    monkeypatch.setattr(
        user_dao, "get_user", lambda session, user_id: SimpleNamespace(user_id=user_id)
    )
    monkeypatch.setattr(store_dao, "get_store", lambda session, store_id: None)

    code, msg, order_id = buyer.new_order("buyer", "missing_store", [("book", 1)])
    assert (code, msg) == error.error_non_exist_store_id("missing_store")
    assert order_id == ""


def test_payment_invalid_status(buyer, monkeypatch):
    order = SimpleNamespace(
        order_id="order",
        user_id="buyer",
        status="paid",
        store_id="store",
        total_price=100,
    )
    monkeypatch.setattr(order_dao, "get_order", lambda session, order_id: order)
    monkeypatch.setattr(
        user_dao, "get_user", lambda session, uid: SimpleNamespace(password="pwd")
    )
    code, msg = buyer.payment("buyer", "pwd", "order")
    assert (code, msg) == error.error_invalid_order_status("order")


def test_payment_missing_seller(buyer, monkeypatch):
    order = SimpleNamespace(
        order_id="order",
        user_id="buyer",
        status="pending",
        store_id="store",
        total_price=10,
    )
    monkeypatch.setattr(order_dao, "get_order", lambda session, order_id: order)

    def fake_get_user(session, uid):
        if uid == "buyer":
            return SimpleNamespace(password="pwd")
        return None

    monkeypatch.setattr(user_dao, "get_user", fake_get_user)
    monkeypatch.setattr(
        store_dao, "get_store", lambda session, sid: SimpleNamespace(owner_id="seller")
    )
    monkeypatch.setattr(user_dao, "change_balance", lambda *args, **kwargs: True)

    code, msg = buyer.payment("buyer", "pwd", "order")
    assert (code, msg) == error.error_non_exist_user_id("seller")


def test_cancel_order_update_exception(buyer, monkeypatch):
    order = SimpleNamespace(
        order_id="order",
        user_id="buyer",
        status="pending",
        store_id="store",
    )
    monkeypatch.setattr(order_dao, "get_order", lambda session, order_id: order)
    monkeypatch.setattr(
        user_dao, "get_user", lambda session, uid: SimpleNamespace(password="pwd")
    )

    items = [SimpleNamespace(book_id="book", count=2)]
    monkeypatch.setattr(order_dao, "get_order_items", lambda session, oid: items)

    calls = {}

    def record_restore(session, store_id, tuples, decrease=False):
        calls["restored"] = (store_id, tuples, decrease)
        return True

    monkeypatch.setattr(order_dao, "adjust_inventory_for_items", record_restore)

    def raise_error(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(order_dao, "update_order_status", raise_error)

    code, msg = buyer.cancel_order("buyer", "pwd", "order")
    assert code == 530
    assert msg == "boom"
    assert calls["restored"][0] == "store"
    assert calls["restored"][1] == [("book", 2)]


def test_cancel_expired_orders(monkeypatch):
    b = buyer_module.Buyer()
    b.session_scope = dummy_session_scope()
    order = SimpleNamespace(order_id="order", store_id="store")
    monkeypatch.setattr(
        order_dao, "find_expired_pending_orders", lambda session, now, cutoff: [order]
    )
    items = [SimpleNamespace(book_id="book", count=1)]
    monkeypatch.setattr(order_dao, "get_order_items", lambda session, oid: items)
    restored = {}


def test_payment_not_sufficient_funds(buyer, monkeypatch):
    order = SimpleNamespace(
        order_id="order",
        user_id="buyer",
        status="pending",
        store_id="store",
        total_price=50,
    )
    monkeypatch.setattr(order_dao, "get_order", lambda session, oid: order)
    monkeypatch.setattr(
        user_dao, "get_user", lambda session, uid: SimpleNamespace(password="pwd")
    )
    monkeypatch.setattr(
        store_dao, "get_store", lambda session, sid: SimpleNamespace(owner_id="seller")
    )

    balances = {}


def test_payment_update_status_failure(buyer, monkeypatch):
    order = SimpleNamespace(
        order_id="order",
        user_id="buyer",
        status="pending",
        store_id="store",
        total_price=10,
    )
    monkeypatch.setattr(order_dao, "get_order", lambda session, oid: order)
    monkeypatch.setattr(
        user_dao, "get_user", lambda session, uid: SimpleNamespace(password="pwd")
    )
    monkeypatch.setattr(
        store_dao, "get_store", lambda session, sid: SimpleNamespace(owner_id="seller")
    )
    monkeypatch.setattr(user_dao, "change_balance", lambda *args, **kwargs: True)
    monkeypatch.setattr(order_dao, "update_order_status", lambda *args, **kwargs: False)

    code, msg = buyer.payment("buyer", "pwd", "order")
    assert (code, msg) == error.error_invalid_order_status("order")

