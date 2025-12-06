import json
from typing import Dict, List, Optional, Tuple

from be.model import db_conn
from be.model.dao import search_dao


class Search(db_conn.DBConn):
    def __init__(self):
        super().__init__()

    def search_books(
        self,
        keyword: Optional[str],
        store_id: Optional[str],
        page: int,
        page_size: int,
    ) -> Tuple[int, str, Dict]:
        safe_page = page if page and page > 0 else 1
        safe_page_size = page_size if page_size and page_size > 0 else 20
        safe_page_size = min(safe_page_size, 50)

        try:
            with self.session_scope() as session:
                total, records = search_dao.search_books(
                    session,
                    keyword=keyword,
                    scope=None,
                    store_id=store_id,
                    page=safe_page,
                    page_size=safe_page_size,
                    sort="updated_at",
                )
                books: List[Dict] = []
                for record in records:
                    inv = record["inventory"]
                    book = record["book"]
                    info_str = getattr(inv, "book_info", "") or "{}"
                    try:
                        info = json.loads(info_str)
                    except (TypeError, ValueError):
                        info = {}
                    books.append(
                        {
                            "store_id": inv.store_id,
                            "book_id": book.book_id,
                            "stock_level": inv.stock_level,
                            "book_info": info,
                        }
                    )
                payload = {
                    "page": safe_page,
                    "page_size": safe_page_size,
                    "total": total,
                    "books": books,
                }
                return 200, "ok", payload
        except BaseException as e:
            return 530, "{}".format(str(e)), {}
