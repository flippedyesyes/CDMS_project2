import os
from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from be.model.models import Book, BookSearchIndex, Inventory

try:
    from sqlalchemy.dialects.mysql import match as mysql_match
except ImportError:  # pragma: no cover
    mysql_match = None

USE_FULLTEXT = mysql_match is not None and os.getenv("BOOKSTORE_DISABLE_FULLTEXT") != "1"


def upsert_search_index(session: Session, book_id: str, **kwargs) -> BookSearchIndex:
    entry = session.get(BookSearchIndex, book_id)
    if entry is None:
        entry = BookSearchIndex(book_id=book_id, **kwargs)
        session.add(entry)
    else:
        for key, value in kwargs.items():
            setattr(entry, key, value)
    session.flush()
    return entry


def search_books(
    session: Session,
    keyword: Optional[str],
    scope: Optional[List[str]],
    store_id: Optional[str],
    page: int,
    page_size: int,
    sort: str,
):
    query = (
        session.query(Inventory, Book, BookSearchIndex)
        .join(Book, Inventory.book_id == Book.book_id)
        .outerjoin(BookSearchIndex, Book.book_id == BookSearchIndex.book_id)
    )
    if store_id:
        query = query.filter(Inventory.store_id == store_id)

    score_column = None
    if keyword:
        column_map = {
            "title": BookSearchIndex.title,
            "author": BookSearchIndex.author,
            "tags": BookSearchIndex.tags,
            "catalog": BookSearchIndex.catalog_excerpt,
            "content": BookSearchIndex.content_excerpt,
            "intro": BookSearchIndex.intro_excerpt,
        }
        fields = scope or ["title", "author", "tags", "catalog", "content", "intro"]
        selected_columns = [column_map.get(f) for f in fields if column_map.get(f) is not None]

        if USE_FULLTEXT and selected_columns:
            base_match = mysql_match(*selected_columns, against=keyword)
            score_column = base_match.label("match_score")
            query = query.filter(base_match.in_boolean_mode())
            query = query.add_columns(score_column)
        else:
            like_expr = f"%{keyword}%"
            filters = [col.ilike(like_expr) for col in selected_columns if col is not None]
            if filters:
                query = query.filter(or_(*filters))

    sort_column = Inventory.updated_at
    if sort == "price":
        sort_column = Inventory.price
    elif sort == "score" and score_column is not None:
        sort_column = score_column

    total = query.count()
    rows = (
        query.order_by(sort_column.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    results = []
    for row in rows:
        if score_column is not None:
            inv, book, index, _score = row
        else:
            inv, book, index = row
        results.append({"inventory": inv, "book": book, "search_index": index})
    return total, results
