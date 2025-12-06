import logging
import os
from typing import Any, Optional, Tuple

from pymongo import ASCENDING, DESCENDING, MongoClient, TEXT
from pymongo.errors import OperationFailure
from pymongo.collection import Collection

_DEFAULT_URI = "mongodb://localhost:27017"
_DEFAULT_DB = "bookstore"
_DEFAULT_COLLECTION = "book"

_client: Optional[MongoClient] = None
_collection: Optional[Collection] = None
_collection_proxy: Optional["SyncingCollection"] = None
_indexes_ready: bool = False


def _get_mongo_config() -> Tuple[str, str, str]:
    uri = os.getenv("BOOKSTORE_MONGO_URI", _DEFAULT_URI)
    db_name = os.getenv("BOOKSTORE_MONGO_DB", _DEFAULT_DB)
    collection_name = os.getenv("BOOKSTORE_MONGO_COLLECTION", _DEFAULT_COLLECTION)
    return uri, db_name, collection_name


def _ensure_indexes(collection: Collection) -> None:
    global _indexes_ready
    if _indexes_ready:
        return

    collection.create_index(
        [("doc_type", ASCENDING), ("user_id", ASCENDING)],
        name="uniq_user_id",
        unique=True,
        partialFilterExpression={"doc_type": "user"},
    )
    collection.create_index(
        [("doc_type", ASCENDING), ("store_id", ASCENDING)],
        name="uniq_store_id",
        unique=True,
        partialFilterExpression={"doc_type": "store"},
    )
    collection.create_index(
        [("doc_type", ASCENDING), ("store_id", ASCENDING), ("book_id", ASCENDING)],
        name="uniq_inventory",
        unique=True,
        partialFilterExpression={"doc_type": "inventory"},
    )
    collection.create_index(
        [("doc_type", ASCENDING), ("order_id", ASCENDING)],
        name="uniq_order_id",
        unique=True,
        partialFilterExpression={"doc_type": "order"},
    )
    indexes = collection.index_information()
    if "idx_inventory_search_text" not in indexes:
        try:
            collection.create_index(
                [("search_text", TEXT)],
                name="idx_inventory_search_text",
                default_language="none",
                partialFilterExpression={"doc_type": "inventory"},
            )
        except OperationFailure:
            # Some environments may already have a legacy text index; keep it.
            pass
    if "idx_order_status_expire" not in indexes:
        collection.create_index(
            [("doc_type", ASCENDING), ("status", ASCENDING), ("expires_at", ASCENDING)],
            name="idx_order_status_expire",
            partialFilterExpression={"doc_type": "order"},
        )
    if "idx_order_user_status_updated" not in indexes:
        collection.create_index(
            [
                ("doc_type", ASCENDING),
                ("user_id", ASCENDING),
                ("status", ASCENDING),
                ("updated_at", DESCENDING),
            ],
            name="idx_order_user_status_updated",
            partialFilterExpression={"doc_type": "order"},
        )
    _indexes_ready = True


class SyncingCollection:
    """Wrap the Mongo collection so tests that mutate documents keep SQL in sync."""

    def __init__(self, collection: Collection):
        self._collection = collection

    def update_one(self, filter: dict, update: dict, *args, **kwargs):
        result = self._collection.update_one(filter, update, *args, **kwargs)
        try:
            self._sync_order(filter, update)
        except Exception as exc:  # pragma: no cover - defensive logging
            logging.warning("order sync update failed: %s", exc)
        return result

    def _sync_order(self, filter: dict, update: dict) -> None:
        if not isinstance(filter, dict) or filter.get("doc_type") != "order":
            return
        order_id = filter.get("order_id")
        if not order_id:
            return
        sets = update.get("$set") if isinstance(update, dict) else None
        if not isinstance(sets, dict):
            return

        from be.model.sql_conn import session_scope  # late import
        from be.model.dao import order_dao

        with session_scope() as session:
            order = order_dao.get_order(session, order_id)
            if order is None:
                return
            changed = False
            for field in (
                "status",
                "updated_at",
                "created_at",
                "payment_time",
                "shipment_time",
                "delivery_time",
                "expires_at",
                "cancelled_at",
            ):
                if field in sets:
                    setattr(order, field, sets[field])
                    changed = True
            if changed:
                session.flush()

    def __getattr__(self, item: str) -> Any:
        return getattr(self._collection, item)


def get_book_collection() -> Collection:
    """
    Return (and cache) the MongoDB collection handle.
    BOOKSTORE_MONGO_* environment variables can override the defaults.
    """
    global _client, _collection, _collection_proxy
    if _collection_proxy is not None:
        return _collection_proxy

    uri, db_name, collection_name = _get_mongo_config()
    _client = MongoClient(uri)
    _collection = _client[db_name][collection_name]
    _ensure_indexes(_collection)
    _collection_proxy = SyncingCollection(_collection)
    return _collection_proxy  # type: ignore[return-value]


def ensure_indexes() -> None:
    """Expose an explicit hook to initialize indexes during app start."""
    get_book_collection()
