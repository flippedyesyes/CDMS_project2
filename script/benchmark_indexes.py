"""Benchmark the effect of MongoDB indexes on key bookstore operations.

Usage:
    python -m script.benchmark_indexes

The script will:
  1. Seed (or reuse) synthetic inventory / order data.
  2. Measure query execution stats for three index configurations:
       - none: drop related indexes.
       - legacy: keep the historical text index only.
       - full: keep all indexes introduced by the project (ensure_indexes()).
  3. Run benchmarks for:
       - Book search (text + store constraint).
       - Pending order scan (status + expires_at).
       - Batch writes (insert_many).
  4. Print results in tabular form.

The script connects to the Mongo database defined by `BOOKSTORE_MONGO_DB`.
"""

from __future__ import annotations

import os
import random
import statistics
import string
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

os.environ.setdefault("BOOKSTORE_MONGO_DB", "booktest")

from pymongo import TEXT
from pymongo.collection import Collection
from pymongo.errors import OperationFailure

from be.model.mongo import ensure_indexes, get_book_collection, _indexes_ready as mongo_indexes_ready
from fe.access.book import BookDB

BOOK_COUNT = 20000
ORDER_COUNT = 5000
SEARCH_KEYWORD = "三毛"
STORE_SAMPLE = "benchmark-store-1"
USER_SAMPLE = "benchmark-user-1"
LEGACY_INDEX_NAME = "book_fulltext"
TEXT_FIELDS = ["title", "book_intro", "content", "tags"]
INDEX_STATES = ["none", "legacy", "full"]


def _random_sentence(prefix: str, idx: int) -> str:
    random.seed(idx)
    tail = "".join(random.choices(string.ascii_lowercase, k=10))
    return f"{prefix} {SEARCH_KEYWORD} {tail}"


def seed_data(collection: Collection) -> None:
    """Populate synthetic documents if they are missing."""
    collection.delete_many({"doc_type": "inventory", "book_id": {"$regex": "^benchmark-"}})
    collection.delete_many({"doc_type": "order", "order_id": {"$regex": "^benchmark-"}})

    inv_count = collection.count_documents({"doc_type": "inventory", "book_id": {"$regex": "^benchmark-"}})
    ord_count = collection.count_documents({"doc_type": "order", "order_id": {"$regex": "^benchmark-"}})

    if inv_count < BOOK_COUNT:
        print(f"[seed] inserting inventory docs ({BOOK_COUNT})...", flush=True)
        db = BookDB(large=True)
        step = 500
        now = datetime.utcnow()
        docs: List[Dict] = []
        inserted = 0
        for offset in range(0, db.get_book_count(), step):
            books = db.get_book_info(offset, step)
            if not books:
                break
            for i, book in enumerate(books):
                doc = {
                    "doc_type": "inventory",
                    "store_id": STORE_SAMPLE if (inserted + i) % 5 == 0 else f"benchmark-store-{(inserted + i) % 100}",
                    "book_id": f"benchmark-book-{getattr(book, 'id', offset + i)}",
                    "book_info": '{"price": %s}' % getattr(book, "price", 0),
                    "stock_level": 20,
                    "title": getattr(book, "title", _random_sentence("Title", inserted + i)),
                    "book_intro": getattr(book, "book_intro", _random_sentence("Intro", inserted + i)),
                    "content": getattr(book, "content", _random_sentence("Content", inserted + i)),
                    "tags": ["benchmark", f"tag-{(inserted + i) % 10}"],
                    "search_text": " ".join(
                        [
                            getattr(book, "title", ""),
                            getattr(book, "book_intro", ""),
                            getattr(book, "content", ""),
                            "benchmark tag",
                        ]
                    ),
                    "created_at": now,
                    "updated_at": now,
                }
                docs.append(doc)
            if docs:
                collection.insert_many(docs, ordered=False)
                inserted += len(docs)
                docs.clear()
            if inserted >= BOOK_COUNT:
                break

    if ord_count < ORDER_COUNT:
        print(f"[seed] inserting order docs ({ORDER_COUNT})...", flush=True)
        now = datetime.utcnow()
        docs = []
        for i in range(ORDER_COUNT):
            docs.append(
                {
                    "doc_type": "order",
                    "order_id": f"benchmark-order-{i}",
                    "user_id": USER_SAMPLE if i % 5 == 0 else f"benchmark-user-{i % 200}",
                    "store_id": STORE_SAMPLE if i % 7 == 0 else f"benchmark-store-{i % 150}",
                    "status": "pending" if i % 3 else "paid",
                    "items": [],
                    "created_at": now,
                    "updated_at": now,
                    "expires_at": now + timedelta(minutes=30),
                }
            )
            if len(docs) >= 2000:
                collection.insert_many(docs, ordered=False)
                docs.clear()
        if docs:
            collection.insert_many(docs, ordered=False)


def drop_index(collection: Collection, name: str) -> None:
    try:
        collection.drop_index(name)
    except OperationFailure:
        pass


def ensure_legacy_text_index(collection: Collection) -> None:
    try:
        collection.create_index(
            [(field, TEXT) for field in TEXT_FIELDS],
            name=LEGACY_INDEX_NAME,
            default_language="none",
            partialFilterExpression={"doc_type": "inventory"},
        )
    except OperationFailure:
        pass


@contextmanager
def index_state(state: str, collection: Collection):
    """
    Configure indexes according to state.

    none   -> drop search/order indexes
    legacy -> keep legacy text index, drop new ones
    full   -> ensure all project indexes
    """
    global mongo_indexes_ready
    mongo_indexes_ready = False
    if state == "none":
        drop_index(collection, "idx_inventory_search_text")
        drop_index(collection, LEGACY_INDEX_NAME)
        drop_index(collection, "idx_order_status_expire")
        drop_index(collection, "idx_order_user_status_updated")
    elif state == "legacy":
        ensure_legacy_text_index(collection)
        drop_index(collection, "idx_inventory_search_text")
        drop_index(collection, "idx_order_status_expire")
        drop_index(collection, "idx_order_user_status_updated")
    elif state == "full":
        ensure_legacy_text_index(collection)
        ensure_indexes()
    else:
        raise ValueError(f"Unknown index state: {state}")
    try:
        yield
    finally:
        mongo_indexes_ready = False
        ensure_indexes()


def _explain_command(
    collection: Collection,
    filter_doc: Dict,
    sort: Dict | None = None,
    limit: int | None = None,
    skip: int | None = None,
) -> Dict:
    cmd: Dict = {
        "explain": {
            "find": collection.name,
            "filter": filter_doc,
            "projection": {"_id": 0},
        },
        "verbosity": "executionStats",
    }
    find_block = cmd["explain"]
    if sort:
        find_block["sort"] = sort
    if limit is not None:
        find_block["limit"] = int(limit)
    if skip is not None:
        find_block["skip"] = int(skip)
    return collection.database.command(cmd)


def explain_search(collection: Collection, state: str) -> Dict:
    base_filter = {
        "doc_type": "inventory",
        "store_id": STORE_SAMPLE,
    }
    if state == "none":
        filter_doc = dict(base_filter)
        filter_doc["search_text"] = {"$regex": SEARCH_KEYWORD, "$options": "i"}
    else:
        filter_doc = dict(base_filter)
        filter_doc["$text"] = {"$search": SEARCH_KEYWORD}
    return _explain_command(
        collection,
        filter_doc,
        sort={"updated_at": -1},
        limit=20,
    )


def explain_pending_orders(collection: Collection) -> Dict:
    return _explain_command(
        collection,
        {
            "doc_type": "order",
            "status": "pending",
            "expires_at": {"$lte": datetime.utcnow() + timedelta(seconds=1)},
        },
        sort={"updated_at": -1},
        limit=20,
    )


def explain_user_orders(collection: Collection) -> Dict:
    return _explain_command(
        collection,
        {
            "doc_type": "order",
            "user_id": USER_SAMPLE,
            "status": "paid",
        },
        sort={"updated_at": -1},
        skip=20,
        limit=20,
    )


def benchmark_write(collection: Collection, batch: List[Dict]) -> float:
    start = time.perf_counter()
    collection.insert_many(batch, ordered=False)
    cost = time.perf_counter() - start
    collection.delete_many({"order_id": {"$in": [doc["order_id"] for doc in batch]}})
    return cost


def summarize(plan: Dict) -> Tuple[str, int, int]:
    winning = plan["queryPlanner"]["winningPlan"]
    stage = winning.get("stage")
    if stage != "SORT":
        name = stage
    else:
        inner = winning.get("inputStage", {})
        while inner.get("stage") in {"SORT", "FETCH"}:
            inner = inner.get("inputStage", {})
        name = inner.get("stage")
    stats = plan.get("executionStats", {})
    return (
        name or "UNKNOWN",
        stats.get("executionTimeMillis", -1),
        stats.get("totalDocsExamined", -1),
    )


def display_results(title: str, rows: List[Tuple[str, Tuple[str, int, int]]]):
    print(f"\n== {title} ==")
    print(f"{'State':<10} | {'Stage':<15} | {'Cost(ms)':>8} | {'DocsExamined':>13}")
    print("-" * 55)
    for state, (stage, cost, docs) in rows:
        print(f"{state:<10} | {stage:<15} | {cost:>8} | {docs:>13}")


def main():
    collection = get_book_collection()
    seed_data(collection)
    search_rows = []
    pending_rows = []
    user_rows = []
    write_rows = []

    batch = [
        {
            "doc_type": "order",
            "order_id": f"bench-write-{i}",
            "user_id": USER_SAMPLE,
            "store_id": STORE_SAMPLE,
            "status": "pending",
            "items": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(minutes=5),
        }
        for i in range(500)
    ]

    for state in INDEX_STATES:
        with index_state(state, collection):
            plan_search = explain_search(collection, state)
            plan_pending = explain_pending_orders(collection)
            plan_user = explain_user_orders(collection)
            write_times = [benchmark_write(collection, batch) for _ in range(3)]

        search_rows.append((state, summarize(plan_search)))
        pending_rows.append((state, summarize(plan_pending)))
        user_rows.append((state, summarize(plan_user)))
        write_rows.append((state, ("N/A", round(statistics.mean(write_times) * 1000), len(batch))))

    display_results("Book Search ($text + store)", search_rows)
    display_results("Pending Orders (status + expires_at)", pending_rows)
    display_results("User Orders (status + updated_at sort)", user_rows)
    print("\n== Batch Insert (500 orders, avg over 3 runs) ==")
    print(f"{'State':<10} | {'AvgCost(ms)':>11}")
    print("-" * 28)
    for state, (_, cost_ms, _) in write_rows:
        print(f"{state:<10} | {cost_ms:>11}")


if __name__ == "__main__":
    main()
