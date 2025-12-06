import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Dict, Optional

from bson.binary import Binary

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from be.model.mongo import get_book_collection  # noqa: E402
from be.model.sql_conn import session_scope  # noqa: E402
from be.model.models import Book, BookSearchIndex, Inventory  # noqa: E402
from be.model.dao import search_dao  # noqa: E402

DEFAULT_SQLITE = Path(__file__).resolve().parents[1] / "fe" / "data" / "book_lx.db"
DEFAULT_LONG_TEXT_THRESHOLD = 2048
DEFAULT_EXCERPT = 512


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import book metadata from SQLite into MySQL using ORM models."
    )
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=DEFAULT_SQLITE,
        help="Path to book.db/book_lx.db (default: fe/data/book.db).",
    )
    parser.add_argument(
        "--long-text-threshold",
        type=int,
        default=DEFAULT_LONG_TEXT_THRESHOLD,
        help="Length above which long text fields are stored to Mongo.",
    )
    parser.add_argument(
        "--excerpt-length",
        type=int,
        default=DEFAULT_EXCERPT,
        help="Length of excerpt kept in MySQL for long text fields.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop existing Book and BookSearchIndex rows before import.",
    )
    return parser.parse_args()


def _excerpt(text: Optional[str], limit: int) -> Optional[str]:
    if not isinstance(text, str):
        return None
    return text if len(text) <= limit else text[:limit]


def import_books(args: argparse.Namespace) -> None:
    sqlite_path = args.sqlite_path.expanduser()
    if not sqlite_path.exists():
        raise SystemExit(f"SQLite file not found: {sqlite_path}")

    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM book")
    rows = cursor.fetchall()

    mongo_coll = get_book_collection()
    imported = 0
    with session_scope() as session:
        if args.reset:
            session.query(Inventory).delete()
            session.query(BookSearchIndex).delete()
            session.query(Book).delete()

        for row in rows:
            data = dict(row)
            book_id = data["id"]
            book = session.get(Book, book_id)
            if book is None:
                book = Book(book_id=book_id)
                session.add(book)

            book.title = data.get("title") or book_id
            book.author = data.get("author")
            book.publisher = data.get("publisher")
            book.original_title = data.get("original_title")
            book.translator = data.get("translator")
            book.pub_year = data.get("pub_year")
            book.pages = data.get("pages")
            book.price = data.get("price")
            book.currency_unit = data.get("currency_unit")
            book.binding = data.get("binding")
            book.isbn = data.get("isbn")

            long_payload: Dict[str, Optional[str]] = {}
            author_intro = data.get("author_intro")
            book_intro = data.get("book_intro")
            content = data.get("content")

            book.author_excerpt = author_intro
            book.intro_excerpt = book_intro
            book.content_excerpt = content

            if author_intro and len(author_intro) > args.long_text_threshold:
                long_payload["author_intro"] = author_intro
                book.author_excerpt = _excerpt(author_intro, args.excerpt_length)
            if book_intro and len(book_intro) > args.long_text_threshold:
                long_payload["book_intro"] = book_intro
                book.intro_excerpt = _excerpt(book_intro, args.excerpt_length)
            if content and len(content) > args.long_text_threshold:
                long_payload["content"] = content
                book.content_excerpt = _excerpt(content, args.excerpt_length)

            picture = data.get("picture")
            if picture:
                long_payload["picture"] = Binary(picture)

            has_blob = bool(long_payload)
            book.has_external_longtext = has_blob

            search_dao.upsert_search_index(
                session,
                book_id,
                title=book.title,
                subtitle=None,
                author=book.author,
                tags=data.get("tags"),
                catalog_excerpt=None,
                intro_excerpt=book.intro_excerpt,
                content_excerpt=book.content_excerpt,
            )

            if has_blob:
                doc = {"doc_type": "book_blob", "book_id": book_id}
                doc.update(
                    {
                        key: value
                        for key, value in long_payload.items()
                        if value is not None
                    }
                )
                mongo_coll.update_one(
                    {"doc_type": "book_blob", "book_id": book_id},
                    {"$set": doc},
                    upsert=True,
                )

            imported += 1

    conn.close()
    print(f"Imported {imported} books from {sqlite_path}")


def main() -> None:
    args = parse_args()
    import_books(args)


if __name__ == "__main__":
    main()
