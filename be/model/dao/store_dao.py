from typing import Optional

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from be.model.models import Book, Bookstore, Inventory


def create_store(
    session: Session,
    store_id: str,
    owner_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Bookstore:
    store = Bookstore(
        store_id=store_id,
        owner_id=owner_id,
        name=name or store_id,
        description=description,
    )
    session.add(store)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise
    return store


def get_store(session: Session, store_id: str) -> Optional[Bookstore]:
    return session.get(Bookstore, store_id)


def upsert_book(session: Session, book_id: str, **kwargs) -> Book:
    book = session.get(Book, book_id)
    if book is None:
        book = Book(book_id=book_id, **kwargs)
        session.add(book)
    else:
        for key, value in kwargs.items():
            setattr(book, key, value)
    session.flush()
    return book


def add_inventory(
    session: Session,
    store_id: str,
    book_id: str,
    stock_level: int,
    price: int,
    book_info: Optional[str] = None,
    search_text: Optional[str] = None,
) -> Inventory:
    inventory = Inventory(
        store_id=store_id,
        book_id=book_id,
        book_info=book_info,
        stock_level=stock_level,
        price=price,
        search_text=search_text,
    )
    session.add(inventory)
    session.flush()
    return inventory


def increase_stock(
    session: Session, store_id: str, book_id: str, delta: int
) -> bool:
    stmt = (
        update(Inventory)
        .where(
            Inventory.store_id == store_id,
            Inventory.book_id == book_id,
        )
        .values(stock_level=Inventory.stock_level + delta)
    )
    result = session.execute(stmt)
    return result.rowcount > 0


def get_inventory(
    session: Session, store_id: str, book_id: str
) -> Optional[Inventory]:
    return (
        session.query(Inventory)
        .filter(
            Inventory.store_id == store_id,
            Inventory.book_id == book_id,
        )
        .one_or_none()
    )
