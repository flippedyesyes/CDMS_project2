import os
from functools import lru_cache
from typing import Optional

from pymongo import ASCENDING, MongoClient

DEFAULT_URI = "mongodb://localhost:27017"
DEFAULT_DB = "bookstore"
DEFAULT_COLLECTION = "book"


@lru_cache()
def _get_client() -> MongoClient:
    uri = os.getenv("BOOKSTORE_MONGO_URI", DEFAULT_URI)
    return MongoClient(uri)


def get_book_collection():
    """Return the Mongo collection storing long text/blob documents."""
    db_name = os.getenv("BOOKSTORE_MONGO_DB", DEFAULT_DB)
    coll_name = os.getenv("BOOKSTORE_MONGO_COLLECTION", DEFAULT_COLLECTION)
    return _get_client()[db_name][coll_name]


def ensure_indexes() -> None:
    """Ensure indexes exist for documents stored in Mongo."""
    coll = get_book_collection()
    coll.create_index([("doc_type", ASCENDING)])
    coll.create_index([("book_id", ASCENDING)], unique=False)
    coll.create_index([("doc_type", ASCENDING), ("book_id", ASCENDING)], unique=True)
