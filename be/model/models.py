from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)

from be.model.sql_conn import Base


def utcnow():
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    user_id = Column(String(128), primary_key=True)
    password = Column(String(128), nullable=False)
    balance = Column(BigInteger, nullable=False, default=0)
    token = Column(String(512), nullable=True)
    terminal = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class Bookstore(Base):
    __tablename__ = "bookstores"

    store_id = Column(String(128), primary_key=True)
    owner_id = Column(String(128), ForeignKey("users.user_id"), nullable=False)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(DateTime, default=utcnow, nullable=False)


class Book(Base):
    __tablename__ = "books"

    book_id = Column(String(64), primary_key=True)
    title = Column(String(512), nullable=False)
    author = Column(String(256), nullable=True)
    publisher = Column(String(256), nullable=True)
    original_title = Column(String(512), nullable=True)
    translator = Column(String(256), nullable=True)
    pub_year = Column(String(16), nullable=True)
    pages = Column(Integer, nullable=True)
    price = Column(BigInteger, nullable=True)
    currency_unit = Column(String(32), nullable=True)
    binding = Column(String(64), nullable=True)
    isbn = Column(String(32), nullable=True)
    intro_excerpt = Column(Text, nullable=True)
    author_excerpt = Column(Text, nullable=True)
    content_excerpt = Column(Text, nullable=True)
    cover_ref = Column(String(256), nullable=True)
    has_external_longtext = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class Inventory(Base):
    __tablename__ = "inventories"
    __table_args__ = (
        Index("idx_inventory_store", "store_id"),
        Index("idx_inventory_book", "book_id"),
    )

    store_id = Column(
        String(128), ForeignKey("bookstores.store_id"), primary_key=True, nullable=False
    )
    book_id = Column(
        String(64), ForeignKey("books.book_id"), primary_key=True, nullable=False
    )
    book_info = Column(Text, nullable=True)
    stock_level = Column(Integer, nullable=False, default=0)
    price = Column(BigInteger, nullable=False, default=0)
    search_text = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class Order(Base):
    __tablename__ = "orders"

    order_id = Column(String(256), primary_key=True)
    user_id = Column(String(128), ForeignKey("users.user_id"), nullable=False)
    store_id = Column(String(128), ForeignKey("bookstores.store_id"), nullable=False)
    status = Column(String(32), nullable=False)
    total_price = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    payment_time = Column(DateTime, nullable=True)
    shipment_time = Column(DateTime, nullable=True)
    delivery_time = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_order_user_status", "user_id", "status"),
        Index("idx_order_status_updated", "status", "updated_at"),
    )


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        UniqueConstraint("order_id", "book_id", name="uq_order_item"),
        Index("idx_order_items_order", "order_id"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    order_id = Column(String(256), ForeignKey("orders.order_id"), nullable=False)
    book_id = Column(String(64), ForeignKey("books.book_id"), nullable=False)
    count = Column(Integer, nullable=False)
    unit_price = Column(BigInteger, nullable=False)


class BookSearchIndex(Base):
    __tablename__ = "book_search_index"

    book_id = Column(String(64), ForeignKey("books.book_id"), primary_key=True)
    title = Column(Text, nullable=True)
    subtitle = Column(Text, nullable=True)
    author = Column(Text, nullable=True)
    tags = Column(Text, nullable=True)
    catalog_excerpt = Column(Text, nullable=True)
    intro_excerpt = Column(Text, nullable=True)
    content_excerpt = Column(Text, nullable=True)
    search_vector = Column(Text, nullable=True)
    store_id = Column(String(128), nullable=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
