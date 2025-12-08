import json
import os
import uuid
from urllib.parse import urljoin

import requests

from fe import conf
from fe.access.new_seller import register_new_seller
from fe.access.book import Book
from be.model.seller import Seller as SellerModel
from be.model.sql_conn import session_scope
from be.model.models import Book as ORMBook


class TestSearchByImage:
    @classmethod
    def setup_class(cls):
        cls.seller_id = f"seller_image_{uuid.uuid4()}"
        cls.store_id = f"store_image_{uuid.uuid4()}"
        cls.password = cls.seller_id
        cls.seller = register_new_seller(cls.seller_id, cls.password)
        assert cls.seller.create_store(cls.store_id) == 200

        mapping_path = os.path.join("test_pictures", "ocr_results.json")
        cls.mapping_path = os.path.abspath(mapping_path)
        os.environ["BOOKSTORE_OCR_CACHE"] = cls.mapping_path
        os.environ["BOOKSTORE_DISABLE_FULLTEXT"] = "1"
        with open(mapping_path, "r", encoding="utf-8") as f:
            cls.records = json.load(f)

        cls._add_books_for_records(cls.records)

    @classmethod
    def _add_books_for_records(cls, records):
        if not records:
            return
        seller_model = SellerModel()
        with session_scope() as session:
            for record in records:
                book_id = record["book_id"]
                orm_book = session.get(ORMBook, book_id)
                assert orm_book is not None, f"book {book_id} not found in database"
                book = Book()
                book.id = orm_book.book_id
                book.title = orm_book.title
                book.author = orm_book.author
                book.publisher = orm_book.publisher
                book.original_title = orm_book.original_title
                book.translator = orm_book.translator
                book.pub_year = orm_book.pub_year
                book.pages = orm_book.pages
                book.price = orm_book.price or 0
                book.currency_unit = orm_book.currency_unit
                book.binding = orm_book.binding
                book.isbn = orm_book.isbn
                book.author_intro = orm_book.author_excerpt
                book.book_intro = orm_book.intro_excerpt
                book.content = orm_book.content_excerpt
                book.tags = []
                book_payload = {
                    "id": book.id,
                    "title": book.title,
                    "author": book.author,
                    "publisher": book.publisher,
                    "translator": book.translator,
                    "pub_year": book.pub_year,
                    "price": book.price,
                    "currency_unit": book.currency_unit,
                    "book_intro": book.book_intro,
                    "author_intro": book.author_intro,
                    "content": book.content,
                    "tags": book.tags,
                }
                code, _ = seller_model.add_book(
                    user_id=cls.seller_id,
                    store_id=cls.store_id,
                    book_id=book_id,
                    book_json_str=json.dumps(book_payload, ensure_ascii=False),
                    stock_level=5,
                )
                assert code == 200

    def test_search_each_image_matches_book(self):
        records = getattr(self, "records", [])
        matched = 0
        url = urljoin(conf.URL, "search/books_by_image")
        for record in records:
            book_id = record["book_id"]
            image_path = os.path.abspath(record["image_path"])
            ocr_text = record["ocr_text"]
            response = requests.post(
                url,
                json={
                    "image_path": image_path,
                    "page_size": 10,
                    "store_id": self.store_id,
                    "ocr_text": ocr_text,
                    "book_id": book_id,
                },
            )
            data = response.json()
            assert response.status_code == 200, data
            books = data.get("books", [])
            assert any(book["book_id"] == book_id for book in books)
            matched += 1
        assert matched == len(records)
