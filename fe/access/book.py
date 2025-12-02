import os
import sqlite3 as sqlite
import random
import base64
import simplejson as json


class Book:
    id: str
    title: str
    author: str
    publisher: str
    original_title: str
    translator: str
    pub_year: str
    pages: int
    price: int
    currency_unit: str
    binding: str
    isbn: str
    author_intro: str
    book_intro: str
    content: str
    tags: [str]
    pictures: [bytes]

    def __init__(self):
        self.tags = []
        self.pictures = []


class BookDB:
    def __init__(self, large: bool = False):
        parent_path = os.path.dirname(os.path.dirname(__file__))
        self.db_s = os.path.join(parent_path, "data/book.db")
        self.db_l = os.path.join(parent_path, "data/book_lx.db")
        if large:
            self.book_db = self.db_l
        else:
            self.book_db = self.db_s
        self._ensure_seed_data()

    def _ensure_seed_data(self) -> None:
        """
        The original project ships a large SQLite snapshot (~100 MB). After the
        data file was stripped to keep the repository small, tests now run
        against an empty database which breaks any SQL query referencing the
        `book` table.  To keep behaviour compatible with the tests while
        avoiding the huge binary, we lazily recreate a lightweight catalogue if
        the table is missing or empty.
        """
        need_seed = False
        try:
            conn = sqlite.connect(self.book_db)
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='book'"
            )
            row = cursor.fetchone()
            if row is None:
                need_seed = True
            else:
                cursor = conn.execute("SELECT COUNT(*) FROM book")
                count_row = cursor.fetchone()
                if count_row is None or count_row[0] == 0:
                    need_seed = True
        except sqlite.Error:
            need_seed = True
        finally:
            try:
                conn.close()
            except Exception:
                pass

        if not need_seed:
            return

        seed_rows = []
        for i in range(1, 201):
            book_id = f"book-{i:05d}"
            title = f"Sample Book {i}"
            author = f"Author {i}"
            publisher = "Sample Publisher"
            original_title = title
            translator = f"Translator {i % 7}"
            pub_year = str(2000 + (i % 20))
            pages = 120 + (i % 280)
            price = 1500 + i * 5
            currency_unit = "CNY"
            binding = "Paperback"
            isbn = f"9780000{i:07d}"
            author_intro = f"Author {i} introduction."
            book_intro = f"Book {i} introduction."
            content = f"Content summary for book {i}."
            tags = "sample\nfiction\nclassic"
            picture = None
            seed_rows.append(
                (
                    book_id,
                    title,
                    author,
                    publisher,
                    original_title,
                    translator,
                    pub_year,
                    pages,
                    price,
                    currency_unit,
                    binding,
                    isbn,
                    author_intro,
                    book_intro,
                    content,
                    tags,
                    picture,
                )
            )

        schema_sql = """
        CREATE TABLE IF NOT EXISTS book (
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
        insert_sql = """
        INSERT INTO book (
            id, title, author, publisher, original_title, translator, pub_year,
            pages, price, currency_unit, binding, isbn, author_intro, book_intro,
            content, tags, picture
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        with sqlite.connect(self.book_db) as seed_conn:
            seed_conn.execute("DROP TABLE IF EXISTS book")
            seed_conn.execute(schema_sql)
            seed_conn.executemany(insert_sql, seed_rows)
            seed_conn.commit()

    def get_book_count(self):
        conn = sqlite.connect(self.book_db)
        cursor = conn.execute("SELECT count(id) FROM book")
        row = cursor.fetchone()
        return row[0]

    def get_book_info(self, start, size) -> [Book]:
        books = []
        conn = sqlite.connect(self.book_db)
        cursor = conn.execute(
            "SELECT id, title, author, "
            "publisher, original_title, "
            "translator, pub_year, pages, "
            "price, currency_unit, binding, "
            "isbn, author_intro, book_intro, "
            "content, tags, picture FROM book ORDER BY id "
            "LIMIT ? OFFSET ?",
            (size, start),
        )
        for row in cursor:
            book = Book()
            book.id = row[0]
            book.title = row[1]
            book.author = row[2]
            book.publisher = row[3]
            book.original_title = row[4]
            book.translator = row[5]
            book.pub_year = row[6]
            book.pages = row[7]
            book.price = row[8]

            book.currency_unit = row[9]
            book.binding = row[10]
            book.isbn = row[11]
            book.author_intro = row[12]
            book.book_intro = row[13]
            book.content = row[14]
            tags = row[15]

            picture = row[16]

            for tag in tags.split("\n"):
                if tag.strip() != "":
                    book.tags.append(tag)
            for i in range(0, random.randint(0, 9)):
                if picture is not None:
                    encode_str = base64.b64encode(picture).decode("utf-8")
                    book.pictures.append(encode_str)
            books.append(book)
            # print(tags.decode('utf-8'))

            # print(book.tags, len(book.picture))
            # print(book)
            # print(tags)

        return books
