import contextlib
import json
from types import SimpleNamespace

import pytest

from be.model import error
from be.model import seller as seller_module
from be.model.dao import order_dao, store_dao


def dummy_session_scope():
    @contextlib.contextmanager
    def _scope():
        yield SimpleNamespace()

    return _scope


def test_parse_book_info_invalid_json():
    assert seller_module._parse_book_info("not json") == {}


def test_collect_search_text_string_tags():
    text, fields = seller_module._collect_search_text({"tags": "科幻"})
    assert "科幻" in text
    assert fields["tags"] == "科幻"


def test_add_book_non_exist_user(monkeypatch):
    s = seller_module.Seller()
    monkeypatch.setattr(seller_module.Seller, "user_id_exist", lambda self, _: False)
    code, _ = s.add_book("missing", "store", "book", json.dumps({"id": "book"}), 1)
    assert code == error.error_non_exist_user_id("missing")[0]


def test_batch_add_books_invalid_payload(monkeypatch):
    s = seller_module.Seller()
    monkeypatch.setattr(seller_module.Seller, "user_id_exist", lambda self, _: True)
    monkeypatch.setattr(seller_module.Seller, "store_id_exist", lambda self, _: True)
    books = [
        {"book_info": "not dict"},
        {"book_info": {"title": "no id"}},
    ]
    code, message, results = s.batch_add_books("u", "s", books)
    assert code == 200
    assert message == "partial failure"
    assert all(item["code"] == 530 for item in results)


def test_add_stock_level_increase_failure(monkeypatch):
    s = seller_module.Seller()
    monkeypatch.setattr(seller_module.Seller, "user_id_exist", lambda self, _: True)
    monkeypatch.setattr(seller_module.Seller, "store_id_exist", lambda self, _: True)
    monkeypatch.setattr(seller_module.Seller, "book_id_exist", lambda self, *_: True)
    s.session_scope = dummy_session_scope()
    monkeypatch.setattr(store_dao, "get_store", lambda session, store_id: SimpleNamespace(owner_id="owner"))
    monkeypatch.setattr(store_dao, "increase_stock", lambda *args, **kwargs: False)
    code, _ = s.add_stock_level("user", "store", "book", 1)
    assert code == error.error_non_exist_book_id("book")[0]


def test_ship_order_wrong_owner(monkeypatch):
    s = seller_module.Seller()
    monkeypatch.setattr(seller_module.Seller, "user_id_exist", lambda self, _: True)
    s.session_scope = dummy_session_scope()
    monkeypatch.setattr(store_dao, "get_store", lambda session, store_id: SimpleNamespace(owner_id="other"))
    code, _ = s.ship_order("user", "store", "order")
    assert code == error.error_authorization_fail()[0]


def test_ship_order_update_status_failure(monkeypatch):
    s = seller_module.Seller()
    monkeypatch.setattr(seller_module.Seller, "user_id_exist", lambda self, _: True)

    def fake_store(session, store_id):
        return SimpleNamespace(owner_id="user")

    def fake_order(session, order_id):
        return SimpleNamespace(store_id="store", status="paid")

    s.session_scope = dummy_session_scope()
    monkeypatch.setattr(store_dao, "get_store", fake_store)
    monkeypatch.setattr(order_dao, "get_order", fake_order)
    monkeypatch.setattr(order_dao, "update_order_status", lambda *args, **kwargs: False)
    code, _ = s.ship_order("user", "store", "order")
    assert code == error.error_invalid_order_status("order")[0]


def test_ship_order_invalid_status(monkeypatch):
    s = seller_module.Seller()
    monkeypatch.setattr(seller_module.Seller, "user_id_exist", lambda self, _: True)
    s.session_scope = dummy_session_scope()
    monkeypatch.setattr(
        store_dao, "get_store", lambda session, store_id: SimpleNamespace(owner_id="user")
    )
    order = SimpleNamespace(store_id="store", status="pending")
    monkeypatch.setattr(order_dao, "get_order", lambda session, order_id: order)
    code, _ = s.ship_order("user", "store", "order")
    assert code == error.error_invalid_order_status("order")[0]


def test_batch_add_books_all_success(monkeypatch):
    s = seller_module.Seller()
    monkeypatch.setattr(seller_module.Seller, "user_id_exist", lambda self, _: True)
    monkeypatch.setattr(seller_module.Seller, "store_id_exist", lambda self, _: True)
    monkeypatch.setattr(seller_module.Seller, "add_book", lambda *args, **kwargs: (200, "ok"))
    books = [
        {"book_info": {"id": "book1"}, "stock_level": 5},
        {"book_info": {"id": "book2"}, "stock_level": 3},
    ]
    code, message, results = s.batch_add_books("u", "s", books)
    assert code == 200
    assert message == "ok"
    assert all(item["code"] == 200 for item in results)


def test_add_book_success(monkeypatch):
    s = seller_module.Seller()
    monkeypatch.setattr(seller_module.Seller, "user_id_exist", lambda self, _: True)
    monkeypatch.setattr(seller_module.Seller, "store_id_exist", lambda self, _: True)
    monkeypatch.setattr(seller_module.Seller, "book_id_exist", lambda self, store, book: False)

    recorded = {}

    def fake_upsert_book(session, book_id, **kwargs):
        recorded["book_id"] = book_id

    monkeypatch.setattr(store_dao, "upsert_book", fake_upsert_book)
    monkeypatch.setattr(store_dao, "add_inventory", lambda *args, **kwargs: None)
    monkeypatch.setattr(seller_module.search_dao, "upsert_search_index", lambda *args, **kwargs: None)

    payload = {
        "id": "book-1",
        "title": "Title",
        "price": 100,
        "tags": ["标签"],
        "book_intro": "Intro",
    }
    code, msg = s.add_book("user", "store", "book-1", json.dumps(payload), 10)
    assert (code, msg) == (200, "ok")
    assert recorded["book_id"] == "book-1"


def test_create_store_success(monkeypatch):
    s = seller_module.Seller()
    monkeypatch.setattr(seller_module.Seller, "user_id_exist", lambda self, _: True)
    monkeypatch.setattr(seller_module.Seller, "store_id_exist", lambda self, store_id: False)
    called = {}

    def fake_create_store(session, store_id, owner_id, name):
        called["store_id"] = store_id
        called["owner_id"] = owner_id

    monkeypatch.setattr(store_dao, "create_store", fake_create_store)
    s.session_scope = dummy_session_scope()
    code, msg = s.create_store("user", "store-new")
    assert (code, msg) == (200, "ok")
    assert called["store_id"] == "store-new"


def test_add_stock_level_success(monkeypatch):
    s = seller_module.Seller()
    monkeypatch.setattr(seller_module.Seller, "user_id_exist", lambda self, _: True)
    monkeypatch.setattr(seller_module.Seller, "store_id_exist", lambda self, _: True)
    monkeypatch.setattr(seller_module.Seller, "book_id_exist", lambda self, store, book: True)
    s.session_scope = dummy_session_scope()
    monkeypatch.setattr(store_dao, "get_store", lambda session, store_id: SimpleNamespace(owner_id="owner"))
    monkeypatch.setattr(store_dao, "increase_stock", lambda *args, **kwargs: True)
    code, msg = s.add_stock_level("user", "store", "book", 5)
    assert (code, msg) == (200, "ok")


def test_ship_order_store_missing(monkeypatch):
    s = seller_module.Seller()
    monkeypatch.setattr(seller_module.Seller, "user_id_exist", lambda self, _: True)
    s.session_scope = dummy_session_scope()
    monkeypatch.setattr(store_dao, "get_store", lambda session, store_id: None)
    code, msg = s.ship_order("user", "store", "order")
    assert (code, msg) == error.error_non_exist_store_id("store")


def test_ship_order_order_missing(monkeypatch):
    s = seller_module.Seller()
    monkeypatch.setattr(seller_module.Seller, "user_id_exist", lambda self, _: True)
    s.session_scope = dummy_session_scope()
    monkeypatch.setattr(
        store_dao, "get_store", lambda session, store_id: SimpleNamespace(owner_id="user")
    )
    monkeypatch.setattr(order_dao, "get_order", lambda session, order_id: None)
    code, msg = s.ship_order("user", "store", "order")
    assert (code, msg) == error.error_invalid_order_id("order")


def test_ship_order_user_missing(monkeypatch):
    s = seller_module.Seller()
    monkeypatch.setattr(seller_module.Seller, "user_id_exist", lambda self, _: False)
    code, msg = s.ship_order("user", "store", "order")
    assert (code, msg) == error.error_non_exist_user_id("user")
