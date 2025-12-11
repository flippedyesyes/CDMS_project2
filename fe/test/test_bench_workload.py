import logging
from types import SimpleNamespace

import pytest

from fe.bench import workload


class DummyBookDB:
    """Provide deterministic book metadata without touching the real sqlite file."""

    def __init__(self):
        self.rows = [SimpleNamespace(id=f"dummy-book-{i}") for i in range(5)]

    def get_book_count(self):
        return len(self.rows)

    def get_book_info(self, start, batch_size):
        return self.rows[start : start + batch_size]


class DummyBuyer:
    """Lightweight Buyer replacement so get_new_order 不需要真实的 HTTP 交互。"""

    def __init__(self, url_prefix, user_id, password):
        self.url = url_prefix
        self.user_id = user_id
        self.password = password

    def new_order(self, store_id, book_id_and_count):
        self.latest_store = store_id
        self.latest_books = book_id_and_count
        return 200, "order-from-dummy"

    def payment(self, order_id):
        return 200


def make_workload(monkeypatch):
    """创建一个可控的 Workload 实例，避免真实的 DB/HTTP 依赖。"""

    monkeypatch.setattr(workload.book, "BookDB", lambda use_large: DummyBookDB())
    wl = workload.Workload()
    wl.store_ids = ["store-deterministic"]
    wl.book_ids = {"store-deterministic": ["dummy-book-0", "dummy-book-1"]}
    wl.buyer_num = 1
    monkeypatch.setattr(workload, "Buyer", DummyBuyer)
    return wl


def test_get_new_order_deterministic(monkeypatch):
    wl = make_workload(monkeypatch)

    # random.randint / uniform 都返回最小值，从而固定选择首个用户/门店/书籍。
    monkeypatch.setattr(workload.random, "randint", lambda a, b: a)
    monkeypatch.setattr(workload.random, "uniform", lambda a, b: 0)

    new_order = wl.get_new_order()

    assert isinstance(new_order, workload.NewOrder)
    assert new_order.store_id == "store-deterministic"
    assert new_order.book_id_and_count == [("dummy-book-0", 1)]

    expected_user, expected_pwd = wl.to_buyer_id_and_password(1)
    assert new_order.buyer.user_id == expected_user
    assert new_order.buyer.password == expected_pwd


def test_update_stat_logs_throughput(monkeypatch, caplog):
    wl = make_workload(monkeypatch)

    with caplog.at_level(logging.INFO):
        wl.update_stat(
            n_new_order=2,
            n_payment=1,
            n_new_order_ok=2,
            n_payment_ok=1,
            time_new_order=0.4,
            time_payment=0.2,
        )

    assert wl.n_new_order == 2
    assert wl.n_payment == 1
    assert wl.n_new_order_ok == 2
    assert wl.n_payment_ok == 1
    assert wl.time_new_order == pytest.approx(0.4)
    assert wl.time_payment == pytest.approx(0.2)
    assert any("TPS_C=" in rec.message for rec in caplog.records)
