import sqlite3 as sqlite
from pathlib import Path

import pytest

from fe.access.book import BookDB


def _make_seeded_db(tmp_path: Path) -> BookDB:
    db_path = tmp_path / "books.db"
    book_db = BookDB.__new__(BookDB)
    book_db.db_s = str(db_path)
    book_db.db_l = str(db_path)
    book_db.book_db = str(db_path)
    book_db._ensure_seed_data()
    return book_db


def test_ensure_seed_data_populates_empty_db(tmp_path):
    book_db = _make_seeded_db(tmp_path)
    with sqlite.connect(book_db.book_db) as conn:
        count = conn.execute("SELECT COUNT(*) FROM book").fetchone()[0]
    assert count == 200


def test_ensure_seed_data_skips_when_table_has_rows(tmp_path):
    db_path = tmp_path / "preseeded.db"
    with sqlite.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE book (
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
            )
            """
        )
        conn.execute(
            """
            INSERT INTO book (
                id, title, author, publisher, original_title, translator, pub_year,
                pages, price, currency_unit, binding, isbn, author_intro, book_intro,
                content, tags, picture
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "book-preseeded",
                "Preseeded Book",
                "Tester",
                "TestPub",
                "Preseeded Book",
                "Translator",
                "2024",
                123,
                1999,
                "CNY",
                "Paperback",
                "9781234567890",
                "Author intro",
                "Book intro",
                "Content",
                "tag1\ntag2",
                None,
            ),
        )
        conn.commit()

    book_db = BookDB.__new__(BookDB)
    book_db.db_s = str(db_path)
    book_db.db_l = str(db_path)
    book_db.book_db = str(db_path)
    book_db._ensure_seed_data()

    with sqlite.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM book").fetchone()[0]
        title = conn.execute(
            "SELECT title FROM book WHERE id = 'book-preseeded'"
        ).fetchone()[0]
    assert count == 1
    assert title == "Preseeded Book"


def test_get_book_info_returns_models(tmp_path, monkeypatch):
    book_db = _make_seeded_db(tmp_path)
    monkeypatch.setattr("fe.access.book.random.randint", lambda a, b: 0)

    books = book_db.get_book_info(0, 5)
    assert len(books) == 5
    first = books[0]
    assert first.id.startswith("book-")
    assert first.tags == ["sample", "fiction", "classic"]
    assert book_db.get_book_count() == 200
