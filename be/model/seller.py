import json
from datetime import datetime
from typing import Dict, Optional, Tuple

from be.model import error, db_conn
from be.model.dao import user_dao, store_dao, order_dao, search_dao


def _parse_book_info(book_json_str: str) -> Dict:
    try:
        obj = json.loads(book_json_str)
        if isinstance(obj, dict):
            return obj
    except (TypeError, ValueError):
        pass
    return {}


def _collect_search_text(book_obj: Dict) -> Tuple[str, Dict[str, Optional[str]]]:
    search_pieces = []
    text_fields: Dict[str, Optional[str]] = {}
    for key in (
        "title",
        "sub_title",
        "author",
        "publisher",
        "translator",
        "book_intro",
        "author_intro",
        "content",
    ):
        value = book_obj.get(key)
        if isinstance(value, str):
            search_pieces.append(value)
            if key in {"title", "book_intro", "content"}:
                text_fields[key] = value
    tags = book_obj.get("tags")
    if isinstance(tags, list):
        joined = ",".join(str(tag) for tag in tags if tag)
        if joined:
            search_pieces.append(joined)
            text_fields["tags"] = joined
    elif isinstance(tags, str):
        search_pieces.append(tags)
        text_fields["tags"] = tags
    catalog = book_obj.get("catalog")
    if isinstance(catalog, str):
        search_pieces.append(catalog)
        text_fields["catalog"] = catalog
    return " ".join(piece for piece in search_pieces if piece), text_fields


def _excerpt(text: Optional[str], limit: int = 512) -> Optional[str]:
    if not isinstance(text, str):
        return None
    return text if len(text) <= limit else text[:limit]


with open("seller_loaded.marker", "a") as _marker:
    _marker.write("loaded\n")


class Seller(db_conn.DBConn):
    def __init__(self):
        super().__init__()

    def add_book(
        self,
        user_id: str,
        store_id: str,
        book_id: str,
        book_json_str: str,
        stock_level: int,
    ):
        try:
            if not self.user_id_exist(user_id):
                return error.error_non_exist_user_id(user_id)
            if not self.store_id_exist(store_id):
                return error.error_non_exist_store_id(store_id)
            if self.book_id_exist(store_id, book_id):
                return error.error_exist_book_id(book_id)

            book_obj = _parse_book_info(book_json_str)
            search_text, text_fields = _collect_search_text(book_obj)
            price = int(book_obj.get("price") or 0)
            title = book_obj.get("title") or book_id

            with self.session_scope() as session:
                store_dao.upsert_book(
                    session,
                    book_id,
                    title=title,
                    author=book_obj.get("author"),
                    publisher=book_obj.get("publisher"),
                    original_title=book_obj.get("original_title"),
                    translator=book_obj.get("translator"),
                    pub_year=book_obj.get("pub_year"),
                    pages=book_obj.get("pages"),
                    price=price,
                    currency_unit=book_obj.get("currency_unit"),
                    binding=book_obj.get("binding"),
                    isbn=book_obj.get("isbn"),
                    intro_excerpt=_excerpt(book_obj.get("book_intro")),
                    author_excerpt=_excerpt(book_obj.get("author_intro")),
                    content_excerpt=_excerpt(book_obj.get("content")),
                )
                store_dao.add_inventory(
                    session,
                    store_id=store_id,
                    book_id=book_id,
                    stock_level=int(stock_level),
                    price=price,
                    book_info=book_json_str,
                    search_text=search_text,
                )
                search_dao.upsert_search_index(
                    session,
                    book_id,
                    title=title,
                    subtitle=book_obj.get("sub_title"),
                    author=book_obj.get("author"),
                    tags=text_fields.get("tags"),
                    catalog_excerpt=_excerpt(text_fields.get("catalog")),
                    intro_excerpt=_excerpt(book_obj.get("book_intro")),
                    content_excerpt=_excerpt(book_obj.get("content")),
                )
            return 200, "ok"
        except Exception as e:
            return 530, f"{e}"

    def add_stock_level(
        self, user_id: str, store_id: str, book_id: str, add_stock_level: int
    ):
        try:
            if not self.user_id_exist(user_id):
                return error.error_non_exist_user_id(user_id)
            if not self.store_id_exist(store_id):
                return error.error_non_exist_store_id(store_id)
            if not self.book_id_exist(store_id, book_id):
                return error.error_non_exist_book_id(book_id)

            with self.session_scope() as session:
                store = store_dao.get_store(session, store_id)
                if store is None:
                    return error.error_non_exist_store_id(store_id)
                success = store_dao.increase_stock(
                    session, store_id, book_id, int(add_stock_level)
                )
                if not success:
                    return error.error_non_exist_book_id(book_id)
            return 200, "ok"
        except Exception as e:
            return 530, f"{e}"

    def create_store(self, user_id: str, store_id: str) -> (int, str):
        try:
            if not self.user_id_exist(user_id):
                return error.error_non_exist_user_id(user_id)
            if self.store_id_exist(store_id):
                return error.error_exist_store_id(store_id)
            with self.session_scope() as session:
                store_dao.create_store(
                    session, store_id=store_id, owner_id=user_id, name=store_id
                )
            return 200, "ok"
        except Exception as e:
            return 530, f"{e}"

    def ship_order(self, user_id: str, store_id: str, order_id: str):
        try:
            if not self.user_id_exist(user_id):
                return error.error_non_exist_user_id(user_id)
            with self.session_scope() as session:
                store = store_dao.get_store(session, store_id)
                if store is None:
                    return error.error_non_exist_store_id(store_id)
                if store.owner_id != user_id:
                    return error.error_authorization_fail()

                order = order_dao.get_order(session, order_id)
                if order is None:
                    return error.error_invalid_order_id(order_id)
                if order.store_id != store_id:
                    return error.error_authorization_fail()
                if order.status != "paid":
                    return error.error_invalid_order_status(order_id)

                updated = order_dao.update_order_status(
                    session,
                    order_id=order_id,
                    expected_status="paid",
                    new_status="shipped",
                    updated_at=datetime.utcnow(),
                    shipment_time=datetime.utcnow(),
                )
                if not updated:
                    return error.error_invalid_order_status(order_id)
            return 200, "ok"
        except Exception as e:
            return 530, f"{e}"
