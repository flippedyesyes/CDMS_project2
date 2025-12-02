"""Normalize `book` and `booklx` collections to the required schema."""

import argparse
from typing import Any, Dict, Iterable, List, Optional

from bson.binary import Binary
from pymongo import MongoClient

DEFAULT_MONGO_URI = "mongodb://localhost:27017"
DEFAULT_DB = "bookstore"
DEFAULT_COLLECTIONS = ["book", "booklx"]

TARGET_FIELDS = [
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
    "tags"
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize MongoDB book collections so every document follows the target schema."
    )
    parser.add_argument("--mongo-uri", default=DEFAULT_MONGO_URI, help="MongoDB connection URI")
    parser.add_argument("--db", default=DEFAULT_DB, help="Database name")
    parser.add_argument(
        "--collections",
        nargs="+",
        default=DEFAULT_COLLECTIONS,
        help="Collection names to normalize",
    )
    return parser.parse_args()


def normalize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Return a new document that contains only the target fields with normalized values."""
    normalized: Dict[str, Any] = {"_id": doc["_id"]}
    normalized["id"] = stringify_id(doc.get("id", doc["_id"]))
    normalized["title"] = doc.get("title")
    normalized["author"] = stringify_scalar(doc.get("author"))
    normalized["publisher"] = doc.get("publisher")
    normalized["original_title"] = doc.get("original_title")
    normalized["translator"] = stringify_scalar(doc.get("translator"))
    normalized["pub_year"] = doc.get("pub_year")
    normalized["pages"] = to_int(doc.get("pages"))
    normalized["price"] = to_int(doc.get("price"))
    normalized["currency_unit"] = doc.get("currency_unit")
    normalized["binding"] = doc.get("binding")
    normalized["isbn"] = doc.get("isbn")
    normalized["author_intro"] = doc.get("author_intro")
    normalized["book_intro"] = doc.get("book_intro")
    normalized["content"] = doc.get("content")
    normalized["tags"] = normalize_tags(doc.get("tags"))
    return normalized


def stringify_id(value: Any) -> str:
    return "" if value is None else str(value)


def stringify_scalar(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        return ",".join(str(item) for item in value if item is not None)
    return str(value)


def normalize_tags(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(tag).strip() for tag in value if str(tag).strip()]
    if isinstance(value, str):
        separators = [",", "\n", ";", " "]
        if any(sep in value for sep in separators):
            raw_parts = value.replace(";", "\n").replace(",", "\n").splitlines()
            return [part.strip() for part in raw_parts if part.strip()]
        return [value.strip()] if value.strip() else []
    if isinstance(value, dict):
        return [str(val).strip() for val in value.values() if str(val).strip()]
    return [str(value).strip()]


def normalize_picture(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Binary):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        return Binary(bytes(value))
    return value


def to_int(value: Any) -> Optional[int]:
    if value in (None, "", "null"):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def ensure_indexes(coll, name: str) -> None:
    """Ensure indexes that support core read paths."""
    print(f"{name}: ensuring indexes...")
    coll.create_index("id", name="id_unique", unique=True, sparse=True)
    coll.create_index(
        [
            ("title", "text"),
            ("tags", "text"),
            ("book_intro", "text"),
            ("content", "text"),
        ],
        name="book_fulltext",
        default_language="none",
    )

def process_collection(coll, name: str) -> None:
    total = coll.count_documents({})
    if total == 0:
        print(f"{name}: collection is empty, skipping.")
        return

    print(f"{name}: normalizing {total} documents...")
    updated = 0
    cursor = coll.find({}, no_cursor_timeout=True)
    try:
        for doc in cursor:
            new_doc = normalize_doc(doc)
            coll.replace_one({"_id": doc["_id"]}, new_doc, upsert=False)
            updated += 1
            if updated % 1000 == 0:
                print(f"{name}: {updated}/{total} documents normalized...")
    finally:
        cursor.close()

    ensure_indexes(coll, name)
    print(f"{name}: done. {updated} documents replaced with normalized schema.")


def main() -> None:
    args = parse_args()
    client = MongoClient(args.mongo_uri)
    try:
        db = client[args.db]
        for coll_name in args.collections:
            process_collection(db[coll_name], f"{args.db}.{coll_name}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
