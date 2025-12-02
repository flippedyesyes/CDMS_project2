import json
from typing import Dict, List, Optional, Tuple

from pymongo import DESCENDING
from pymongo.errors import PyMongoError

from be.model import db_conn


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
        query: Dict = {"doc_type": "inventory"}
        if store_id:
            query["store_id"] = store_id

        projection = {
            "_id": 0,
            "store_id": 1,
            "book_id": 1,
            "book_info": 1,
            "stock_level": 1,
            "updated_at": 1,
        }

        try:
            cursor = None
            if keyword:
                query["$text"] = {"$search": keyword}
                projection["score"] = {"$meta": "textScore"}
                cursor = (
                    self.collection.find(query, projection)
                    .sort([("score", {"$meta": "textScore"}), ("updated_at", DESCENDING)])
                )
            else:
                cursor = self.collection.find(query, projection).sort(
                    [("updated_at", DESCENDING)]
                )

            total = self.collection.count_documents(query)
            skip = (safe_page - 1) * safe_page_size
            cursor = cursor.skip(skip).limit(safe_page_size)

            books: List[Dict] = []
            for doc in cursor:
                info_str = doc.get("book_info", "{}")
                try:
                    info = json.loads(info_str)
                except (TypeError, ValueError):
                    info = {}
                result = {
                    "store_id": doc.get("store_id"),
                    "book_id": doc.get("book_id"),
                    "stock_level": doc.get("stock_level", 0),
                    "book_info": info,
                }
                if "score" in doc:
                    result["score"] = doc["score"]
                books.append(result)

            payload = {
                "page": safe_page,
                "page_size": safe_page_size,
                "total": total,
                "books": books,
            }
            return 200, "ok", payload
        except PyMongoError as e:
            return 528, "{}".format(str(e)), {}
        except BaseException as e:
            return 530, "{}".format(str(e)), {}
