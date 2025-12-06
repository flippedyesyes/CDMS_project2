from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from be.model.models import Book, BookSearchIndex, Inventory


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

    if keyword:
        like_expr = f"%{keyword}%"
        filters = []
        fields = scope or ["title", "author", "tags", "catalog", "content"]
        for field in fields:
            if field == "title":
                filters.append(Book.title.ilike(like_expr))
            elif field == "author":
                filters.append(Book.author.ilike(like_expr))
            elif field == "tags":
                filters.append(BookSearchIndex.tags.ilike(like_expr))
            elif field == "catalog":
                filters.append(BookSearchIndex.catalog_excerpt.ilike(like_expr))
            elif field == "content":
                filters.append(BookSearchIndex.content_excerpt.ilike(like_expr))
        if filters:
            query = query.filter(or_(*filters))

    sort_column = Inventory.updated_at
    if sort == "price":
        sort_column = Inventory.price
    elif sort == "score" and keyword:
        sort_column = Inventory.updated_at  # placeholder

    total = query.count()
    rows = (
        query.order_by(sort_column.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    results = []
    for inv, book, index in rows:
        results.append({"inventory": inv, "book": book, "search_index": index})
    return total, results
