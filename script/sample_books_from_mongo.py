"""Sample a subset of MongoDB documents and mirror them into SQLite."""

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from bson.binary import Binary
from pymongo import MongoClient

DEFAULT_MONGO_URI = "mongodb://localhost:27017"
DEFAULT_DB = "bookstore"
DEFAULT_SOURCE_COLLECTION = "booklx"
DEFAULT_TARGET_COLLECTION = "book"
DEFAULT_SAMPLE_SIZE = 5000
DEFAULT_SQLITE_DB = "fe/data/book.db"

BOOK_TABLE_SCHEMA = """
    CREATE TABLE IF NOT EXISTS book
    (
        id TEXT PRIMARY KEY,
        title TEXT,
        author TEXT,
        publisher TEXT,
        original_title TEXT,
        translator TEXT,
        pub_year TEXT,
        pages INTEGER,
        price INTEGER,
        currency_unit TEXT,
        binding TEXT,
        isbn TEXT,
        author_intro TEXT,
        book_intro TEXT,
        content TEXT,
        tags TEXT,
        picture BLOB
    );
"""

BOOK_COLUMNS = [
    "id",
    "title",
    "author",
    "publisher",
    "original_title",
    "translator",
    "pub_year",
    "pages",
    "price",
    "currency_unit",
    "binding",
    "isbn",
    "author_intro",
    "book_intro",
    "content",
    "tags",
    "picture",
]

INSERT_PLACEHOLDERS = ",".join("?" for _ in BOOK_COLUMNS)
INSERT_SQL = (
    f"INSERT OR REPLACE INTO book ({', '.join(BOOK_COLUMNS)}) "
    f"VALUES ({INSERT_PLACEHOLDERS})"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sample documents from MongoDB and export them into SQLite."
    )
    parser.add_argument("--mongo-uri", default=DEFAULT_MONGO_URI, help="MongoDB connection URI")
    parser.add_argument("--db", default=DEFAULT_DB, help="MongoDB database name")
    parser.add_argument("--source", default=DEFAULT_SOURCE_COLLECTION, help="Source collection")
    parser.add_argument("--target", default=DEFAULT_TARGET_COLLECTION, help="Target collection")
    parser.add_argument(
        "--size",
        type=int,
        default=DEFAULT_SAMPLE_SIZE,
        help="Number of documents to sample (caps at source size)",
    )
    parser.add_argument(
        "--query",
        help="Optional JSON filter, e.g. '{\"tags\": {\"$exists\": true}}'",
    )
    parser.add_argument(
        "--keep-target",
        action="store_true",
        help="Keep existing target documents (default drops the collection first)",
    )
    parser.add_argument(
        "--sqlite-db",
        default=DEFAULT_SQLITE_DB,
        help="Output SQLite database path",
    )
    return parser.parse_args()


def load_query(query_str: Optional[str]) -> Dict[str, Any]:
    if not query_str:
        return {}
    try:
        data = json.loads(query_str)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid query JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("Query JSON must be an object, e.g. {'author': 'xxx'}.")
    return data


def sample_and_copy(
    client: MongoClient,
    *,
    db_name: str,
    source_name: str,
    target_name: str,
    sample_size: int,
    drop_target: bool,
    query: Dict[str, Any],
) -> Optional[List[Dict[str, Any]]]:
    if sample_size <= 0:
        raise SystemExit("--size must be a positive integer.")

    db = client[db_name]
    source = db[source_name]
    target = db[target_name]

    total = source.count_documents(query)
    if total == 0:
        print(f"{db_name}.{source_name} has no documents that match the query; abort.")
        return None

    actual_size = min(sample_size, total)
    pipeline: List[Dict[str, Any]] = []
    if query:
        pipeline.append({"$match": query})
    pipeline.append({"$sample": {"size": actual_size}})

    docs = list(source.aggregate(pipeline))
    if not docs:
        print("Aggregation returned no documents.")
        return None

    if drop_target:
        target.drop()

    target.insert_many(docs, ordered=False)
    print(
        f"Sampled {len(docs)} documents from {db_name}.{source_name} "
        f"into {db_name}.{target_name}"
    )
    return docs


def export_to_sqlite(docs: List[Dict[str, Any]], sqlite_db_path: str) -> None:
    sqlite_path = Path(sqlite_db_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(sqlite_path))
    cursor = conn.cursor()

    cursor.execute(BOOK_TABLE_SCHEMA)
    cursor.execute("DELETE FROM book")

    count = 0
    for doc in docs:
        try:
            row = build_row_values(doc)
            cursor.execute(INSERT_SQL, row)
            count += 1
        except Exception as exc:  # pragma: no cover - only logs for visibility
            print(f"Failed to save a document: {exc}")

    conn.commit()
    conn.close()
    print(f"Wrote {count} rows into SQLite database {sqlite_path}")


def build_row_values(doc: Dict[str, Any]) -> List[Any]:
    normalized = dict(doc)
    if "id" not in normalized and "_id" in normalized:
        normalized["id"] = str(normalized["_id"])

    normalized["author"] = stringify_field(normalized.get("author"))
    normalized["translator"] = stringify_field(normalized.get("translator"))
    normalized["tags"] = stringify_field(normalized.get("tags"))
    normalized["pages"] = to_int(normalized.get("pages"))
    normalized["price"] = to_int(normalized.get("price"))
    normalized["picture"] = convert_picture(normalized.get("picture"))

    return [normalized.get(col) for col in BOOK_COLUMNS]


def stringify_field(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: List[str] = []
        for item in value:
            if isinstance(item, dict):
                parts.append(str(item.get("title") or item.get("name") or item))
            else:
                parts.append(str(item))
        return ",".join(parts)
    if isinstance(value, dict):
        return ",".join(f"{k}:{v}" for k, v in value.items())
    return str(value)


def to_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(str(value)))
        except (TypeError, ValueError):
            return None


def convert_picture(value: Any) -> Optional[bytes]:
    if value is None:
        return None
    if isinstance(value, Binary):
        return bytes(value)
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    return value


def main() -> None:
    args = parse_args()
    query = load_query(args.query)
    drop_target = not args.keep_target

    client = MongoClient(args.mongo_uri)
    try:
        docs = sample_and_copy(
            client,
            db_name=args.db,
            source_name=args.source,
            target_name=args.target,
            sample_size=args.size,
            drop_target=drop_target,
            query=query,
        )
        if docs:
            export_to_sqlite(docs, args.sqlite_db)
    finally:
        client.close()


if __name__ == "__main__":
    main()
