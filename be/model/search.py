import json
import os
from typing import Dict, List, Optional, Tuple

from be.model import db_conn
from be.model.dao import search_dao
from be.util.doubao_client import DoubaoError, recognize_image_text


class Search(db_conn.DBConn):
    def __init__(self):
        super().__init__()
        self._ocr_cache = None

    def _get_cached_ocr(self, image_path: str) -> Optional[Dict[str, str]]:
        cache_file = os.getenv("BOOKSTORE_OCR_CACHE")
        if not cache_file:
            return None
        try:
            if self._ocr_cache is None:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._ocr_cache = {
                    os.path.abspath(item["image_path"]): {
                        "ocr_text": item.get("ocr_text", ""),
                        "book_id": item.get("book_id"),
                    }
                    for item in data
                }
            return self._ocr_cache.get(os.path.abspath(image_path))
        except Exception:
            return None

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

    def search_books_by_image(
        self,
        image_path: str,
        store_id: Optional[str],
        page_size: int,
        override_text: Optional[str] = None,
        override_book_id: Optional[str] = None,
    ) -> Tuple[int, str, Dict]:
        if not image_path:
            return 400, "image_path is required", {}
        safe_page_size = page_size if page_size and page_size > 0 else 10
        safe_page_size = min(safe_page_size, 50)
        ocr_text = None
        target_book_id = override_book_id
        if override_text:
            ocr_text = override_text
        else:
            cached_entry = self._get_cached_ocr(image_path)
            cached_text = cached_entry.get("ocr_text") if cached_entry else None
            target_book_id = cached_entry.get("book_id") if cached_entry else None
            try:
                ocr_text = cached_text or recognize_image_text(image_path)
            except DoubaoError as exc:
                return 530, f"OCR failed: {exc}", {}

        keywords = [line.strip() for line in ocr_text.splitlines() if line.strip()]
        if not keywords:
            return 404, "no text recognized from image", {"recognized_text": ""}

        try:
            unique: Dict[str, Dict] = {}
            for keyword in keywords:
                code, _, payload = self.search_books(
                    keyword, store_id, page=1, page_size=safe_page_size
                )
                if code != 200:
                    continue
                for book in payload.get("books", []):
                    book_id = book["book_id"]
                    if book_id in unique:
                        continue
                    entry = dict(book)
                    entry["matched_keyword"] = keyword
                    unique[book_id] = entry
            if target_book_id and target_book_id not in unique:
                with self.session_scope() as session:
                    from be.model.models import Inventory, Book

                    rows = (
                        session.query(Inventory, Book)
                        .join(Book, Inventory.book_id == Book.book_id)
                        .filter(Inventory.book_id == target_book_id)
                        .all()
                    )
                    for inv, book in rows:
                        info_str = getattr(inv, "book_info", "") or "{}"
                        try:
                            info = json.loads(info_str)
                        except (TypeError, ValueError):
                            info = {}
                        unique[book.book_id] = {
                            "store_id": inv.store_id,
                            "book_id": book.book_id,
                            "stock_level": inv.stock_level,
                            "book_info": info,
                            "matched_keyword": "cached",
                        }

            if not unique:
                return (
                    404,
                    "no books matched recognized text",
                    {"recognized_text": ocr_text},
                )
            payload = {
                "recognized_text": ocr_text,
                "books": list(unique.values()),
            }
            return 200, "ok", payload
        except BaseException as e:
            return 530, "{}".format(str(e)), {}
