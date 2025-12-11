import sqlite3

from fe.access.book import BookDB


def test_ensure_seed_data_creates_table(tmp_path):
    temp_db = tmp_path / "seed.db"
    db = BookDB()
    db.book_db = str(temp_db)
    db._ensure_seed_data()
    assert temp_db.exists()
    with sqlite3.connect(temp_db) as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM book")
        count = cursor.fetchone()[0]
    assert count == 200
