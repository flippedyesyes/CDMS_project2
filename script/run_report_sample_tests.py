"""Run scenario-based tests to verify implemented functionality and emit markdown tables."""

from __future__ import annotations

import contextlib
import pathlib
import sys
import threading
import uuid
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import requests
from urllib.parse import urljoin

# Ensure project root is importable when executed as a script.
ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from be import serve  # noqa: E402
from be.model.store import init_completed_event  # noqa: E402
from fe import conf  # noqa: E402
from fe.access.book import Book  # noqa: E402
from fe.access.new_buyer import register_new_buyer  # noqa: E402
from fe.access.new_seller import register_new_seller  # noqa: E402
from fe.access.search import Search  # noqa: E402


class ReportBuilder:
    def __init__(self):
        # {section: {label: [rows]}}
        self._data: Dict[str, Dict[Optional[str], List[Tuple[str, str, str]]]] = defaultdict(
            lambda: defaultdict(list)
        )

    def add_row(
        self,
        section: str,
        label: Optional[str],
        case: str,
        params: str,
        success: bool,
        detail: str,
    ):
        status = "PASS" if success else "FAIL"
        self._data[section][label].append((case, params, f"{status} ({detail})"))

    def render_table(self, rows: List[Tuple[str, str, str]]) -> str:
        header = "| 测试情况 | 传参 | 结果 message |"
        separator = "| --- | --- | --- |"
        body = "\n".join(f"| {case} | {params} | {result} |" for case, params, result in rows)
        return "\n".join([header, separator, body])

    def to_markdown(self) -> str:
        lines: List[str] = []
        for section, tables in self._data.items():
            lines.append(f"- {section}\n")
            for label, rows in tables.items():
                if label:
                    lines.append(f"  - {label}\n")
                table_md = self.render_table(rows)
                lines.append("  " + table_md.replace("\n", "\n  "))
                lines.append("")
        return "\n".join(lines).rstrip()


@contextlib.contextmanager
def run_backend():
    thread = threading.Thread(target=serve.be_run, daemon=True)
    thread.start()
    init_completed_event.wait()
    try:
        yield
    finally:
        shutdown_url = urljoin(conf.URL, "shutdown")
        with contextlib.suppress(Exception):
            requests.get(shutdown_url, timeout=2)
        thread.join()


def make_book(keyword: str, suffix: str) -> Book:
    book = Book()
    unique = uuid.uuid4().hex[:8]
    book.id = f"{keyword}_{suffix}_{unique}"
    book.title = f"{keyword} 样例图书 {suffix}"
    book.author = f"作者 {suffix}"
    book.publisher = "样例出版社"
    book.book_intro = f"{keyword} - 主题简介 {suffix}"
    book.author_intro = f"{keyword} 作者介绍 {suffix}"
    book.content = f"{keyword} 内容预览段落 {suffix}"
    book.translator = f"译者 {suffix}"
    book.pub_year = "2024"
    book.pages = 256
    book.price = 4900
    book.currency_unit = "CNY"
    book.binding = "精装"
    book.isbn = f"9781234{unique[:5]}"
    book.tags = [keyword, "袁氏", "心灵"]
    book.catalog = f"{keyword} 目录 {suffix}"
    return book


def format_details(**kwargs) -> str:
    return ", ".join(f"{k}={v}" for k, v in kwargs.items())


def run_search_tests(report: ReportBuilder, search_client: Search, keyword: str):
    section = "搜索 search"

    def record(case, params, success, **details):
        report.add_row(section, None, case, params, success, format_details(**details))

    def record_multi(case, params, success, **details):
        report.add_row(section, "多关键词搜索", case, params, success, format_details(**details))

    status, data = search_client.books(keyword, page=0, page_size=1)
    record("分页查询", f'("{keyword}", 0)', status == 200, code=status, total=data.get("total"))

    status, data = search_client.books(keyword, page=1, page_size=10)
    record("全部显示查询", f'("{keyword}", 1)', status == 200, code=status, total=data.get("total"))

    missing_kw = f"{keyword}+"
    status, data = search_client.books(f'"{missing_kw}"', page=1, page_size=10)
    record(
        "不存在的关键词",
        f'("{missing_kw}", 1)',
        status == 200 and not data.get("books"),
        code=status,
        total=data.get("total"),
    )

    status, data = search_client.books(keyword, page=1000, page_size=10)
    record(
        "空页",
        f'("{keyword}", 1000)',
        status == 200 and not data.get("books"),
        code=status,
        total=data.get("total"),
    )

    status, data = search_client.books(f'"{missing_kw}"', page=1000, page_size=10)
    record(
        "不存在的关键词 + 空页",
        f'("{missing_kw}", 1000)',
        status == 200 and not data.get("books"),
        code=status,
        total=data.get("total"),
    )

    multi_kw = f"{keyword} 袁氏"
    status, data = search_client.books(multi_kw, page=1, page_size=10)
    record_multi(
        "查询成功",
        "[\"三毛\", \"袁氏\"]",
        status == 200 and data.get("books"),
        code=status,
        total=data.get("total"),
    )

    multi_kw_plus = f"{keyword} 袁氏 心灵"
    status, data = search_client.books(multi_kw_plus, page=1, page_size=10)
    record_multi(
        "查询成功（含额外关键字）",
        "[\"三毛\", \"袁氏\", \"心灵\"]",
        status == 200 and data.get("books"),
        code=status,
        total=data.get("total"),
    )

    mixed_kw = f"{keyword} 袁氏++"
    status, data = search_client.books(mixed_kw, page=1, page_size=10)
    record_multi(
        "含不存在的关键词查询",
        "[\"三毛\", \"袁氏++\"]",
        status == 200 and data.get("books"),
        code=status,
        total=data.get("total"),
    )

    none_kw = f"\"{keyword}++\" \"袁氏++\""
    status, data = search_client.books(none_kw, page=1, page_size=10)
    record_multi(
        "不存在关键词",
        "[\"三毛++\", \"袁氏++\"]",
        status == 200 and not data.get("books"),
        code=status,
        total=data.get("total"),
    )


def make_order_helpers(
    buyer, seller, store_id: str, book_id: str, buyer_password: str
):
    def new_order():
        status, order_id = buyer.new_order(store_id, [(book_id, 1)])
        return status, order_id

    def pay(order_id: str):
        return buyer.payment(order_id)

    def ship(order_id: str, target_store: Optional[str] = None):
        return seller.ship_order(target_store or store_id, order_id)

    def confirm(order_id: str):
        return buyer.confirm_receipt(order_id)

    def cancel(order_id: str):
        return buyer.cancel_order(order_id, password=buyer_password)

    return new_order, pay, ship, confirm, cancel


def run_send_books_tests(
    report: ReportBuilder, buyer, seller, store_id: str, book_id: str, buyer_password: str
):
    section = "发货 send_books"
    new_order, pay, ship, _, cancel = make_order_helpers(
        buyer, seller, store_id, book_id, buyer_password
    )

    def record(case, params, success, **details):
        report.add_row(section, None, case, params, success, format_details(**details))

    # 付款后发货成功
    status, order_id = new_order()
    pay_code = pay(order_id)
    ship_code = ship(order_id)
    record(
        "付款后发货成功",
        "(store_id, order_id)",
        status == 200 and pay_code == 200 and ship_code == 200,
        new=status,
        pay=pay_code,
        ship=ship_code,
    )

    # 未付款无法发货
    status, order_id = new_order()
    ship_code = ship(order_id)
    record(
        "未付款无法发货",
        "(store_id, 未付款 order_id)",
        status == 200 and ship_code != 200,
        new=status,
        ship=ship_code,
    )
    cancel(order_id)

    # 发货不存在的书 / 订单（使用随机订单号）
    random_order = f"missing-{uuid.uuid4()}"
    ship_code = ship(random_order)
    record(
        "发货不存在的书",
        "(store_id, 错误 book_id)",
        ship_code != 200,
        ship=ship_code,
        order=random_order,
    )

    random_order = f"missing-{uuid.uuid4()}"
    ship_code = ship(random_order)
    record(
        "发货不存在的订单",
        "(store_id, 错误 order_id)",
        ship_code != 200,
        ship=ship_code,
        order=random_order,
    )

    # 店铺不存在
    status, order_id = new_order()
    pay_code = pay(order_id)
    ship_code = ship(order_id, target_store=f"{store_id}_ghost")
    record(
        "店铺不存在",
        "(错误 store_id, order_id)",
        status == 200 and pay_code == 200 and ship_code != 200,
        new=status,
        pay=pay_code,
        ship=ship_code,
    )
    # 清理：正常发货并确认
    ship(order_id)
    buyer.confirm_receipt(order_id)


def run_receive_books_tests(
    report: ReportBuilder, buyer, seller, store_id: str, book_id: str, buyer_password: str
):
    section = "收货 receive_books"
    new_order, pay, ship, confirm, cancel = make_order_helpers(
        buyer, seller, store_id, book_id, buyer_password
    )

    def record(case, params, success, **details):
        report.add_row(section, None, case, params, success, format_details(**details))

    # 成功收货
    status, order_id = new_order()
    pay_code = pay(order_id)
    ship_code = ship(order_id)
    confirm_code = confirm(order_id)
    record(
        "付款成功且发货成功后收货",
        "(buyer_id, password, order_id)",
        all(code == 200 for code in (status, pay_code, ship_code, confirm_code)),
        new=status,
        pay=pay_code,
        ship=ship_code,
        confirm=confirm_code,
    )

    # 未付款订单
    status, order_id = new_order()
    confirm_code = confirm(order_id)
    record(
        "未付款订单",
        "(buyer_id, 错误状态 order_id)",
        status == 200 and confirm_code != 200,
        new=status,
        confirm=confirm_code,
    )
    cancel(order_id)

    # 买家不存在（伪造 user_id）
    status, order_id = new_order()
    pay(order_id)
    ship(order_id)
    payload = {"user_id": f"ghost-{uuid.uuid4()}", "order_id": order_id}
    headers = {"token": buyer.token}
    resp = requests.post(
        urljoin(conf.URL, "buyer/confirm_receipt"), headers=headers, json=payload, timeout=5
    )
    record(
        "买家不存在",
        "(不存在的 buyer_id)",
        resp.status_code != 200,
        http_code=resp.status_code,
    )
    confirm(order_id)

    # 订单不存在
    random_order = f"missing-{uuid.uuid4()}"
    confirm_code = confirm(random_order)
    record(
        "订单不存在",
        "(buyer_id, 不存在的 order_id)",
        confirm_code != 200,
        confirm=confirm_code,
    )


def run_buyer_order_queries(
    report: ReportBuilder, buyer, seller, store_id: str, book_id: str, buyer_password: str
):
    current_section = "买家查询当前订单"
    history_section = "买家查询历史订单"
    new_order, pay, ship, confirm, _ = make_order_helpers(
        buyer, seller, store_id, book_id, buyer_password
    )

    def record_current(case, params, success, **details):
        report.add_row(current_section, None, case, params, success, format_details(**details))

    def record_history(case, params, success, **details):
        report.add_row(history_section, None, case, params, success, format_details(**details))

    # 下单 -> 历史为空
    status, order_id = new_order()
    hist_status, hist_data = buyer.list_orders(status="delivered")
    record_history(
        "下单后查询历史订单，空",
        "(buyer_id)",
        hist_status == 200 and hist_data.get("total", 0) == 0,
        code=hist_status,
        total=hist_data.get("total"),
    )

    list_status, data = buyer.list_orders(status="pending")
    record_current(
        "下单后查询当前订单",
        "(buyer_id)",
        list_status == 200 and data.get("total", 0) >= 1,
        code=list_status,
        total=data.get("total"),
    )

    pay(order_id)
    ship(order_id)
    list_status, data = buyer.list_orders(status="shipped")
    record_current(
        "发货后查询当前订单",
        "(buyer_id)",
        list_status == 200 and data.get("total", 0) >= 1,
        code=list_status,
        total=data.get("total"),
    )

    hist_status, hist_data = buyer.list_orders(status="delivered")
    record_history(
        "发货后查询历史订单，空",
        "(buyer_id)",
        hist_status == 200 and hist_data.get("total", 0) == 0,
        code=hist_status,
        total=hist_data.get("total"),
    )

    confirm(order_id)
    list_status, data = buyer.list_orders(status="pending")
    record_current(
        "收货后查询当前订单，为空",
        "(buyer_id)",
        list_status == 200 and data.get("total", 0) == 0,
        code=list_status,
        total=data.get("total"),
    )

    list_status, data = buyer.list_orders(status="delivered")
    record_history(
        "收货后查询历史订单",
        "(buyer_id)",
        list_status == 200 and data.get("total", 0) >= 1,
        code=list_status,
        total=data.get("total"),
    )


def main():
    report = ReportBuilder()
    keyword = "三毛"

    with run_backend():
        seller_id = f"seller-{uuid.uuid4()}"
        seller_pwd = "seller-pass"
        seller = register_new_seller(seller_id, seller_pwd)
        store_id = f"store-{uuid.uuid4()}"
        assert seller.create_store(store_id) == 200

        book = make_book(keyword, "primary")
        assert seller.add_book(store_id, 50, book) == 200

        # 第二个店铺用于全局搜索覆盖
        other_seller_id = f"seller-{uuid.uuid4()}"
        other_pwd = "seller-pass"
        other_seller = register_new_seller(other_seller_id, other_pwd)
        other_store_id = f"store-{uuid.uuid4()}"
        assert other_seller.create_store(other_store_id) == 200
        other_book = make_book(keyword, "secondary")
        assert other_seller.add_book(other_store_id, 20, other_book) == 200

        search_client = Search(conf.URL)
        run_search_tests(report, search_client, keyword)

        # 买家 A：用于发货 / 收货测试
        buyer_ship_id = f"buyer-ship-{uuid.uuid4()}"
        buyer_ship_pwd = "buyer-pass"
        buyer_ship = register_new_buyer(buyer_ship_id, buyer_ship_pwd)
        buyer_ship.add_funds("100000")

        run_send_books_tests(report, buyer_ship, seller, store_id, book.id, buyer_ship_pwd)
        run_receive_books_tests(report, buyer_ship, seller, store_id, book.id, buyer_ship_pwd)

        # 买家 B：用于查询订单
        buyer_list_id = f"buyer-list-{uuid.uuid4()}"
        buyer_list_pwd = "buyer-pass"
        buyer_list = register_new_buyer(buyer_list_id, buyer_list_pwd)
        buyer_list.add_funds("100000")
        run_buyer_order_queries(report, buyer_list, seller, store_id, book.id, buyer_list_pwd)

    print(report.to_markdown())


if __name__ == "__main__":
    main()
