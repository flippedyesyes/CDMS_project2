import json
import uuid
from urllib.parse import urljoin

import requests

from fe import conf
from fe.access.book import Book
from fe.access.new_buyer import register_new_buyer
from fe.access.new_seller import register_new_seller


class TestRecommendByTags:
    @classmethod
    def setup_class(cls):
        cls.seller_id = f"seller_reco_{uuid.uuid4()}"
        cls.store_id = f"store_reco_{uuid.uuid4()}"
        cls.buyer_id = f"buyer_reco_{uuid.uuid4()}"
        cls.password = "password"
        cls.seller = register_new_seller(cls.seller_id, cls.password)
        assert cls.seller.create_store(cls.store_id) == 200

        cls.books = [
            {
                "book_id": f"book-reco-{uuid.uuid4()}",
                "title": "悬疑冒险故事",
                "tags": ["悬疑", "冒险"],
                "price": 3000,
            },
            {
                "book_id": f"book-reco-{uuid.uuid4()}",
                "title": "悬疑科幻故事",
                "tags": ["悬疑", "科幻"],
                "price": 2500,
            },
            {
                "book_id": f"book-reco-{uuid.uuid4()}",
                "title": "都市浪漫故事",
                "tags": ["言情"],
                "price": 2000,
            },
        ]
        cls._add_books()
        cls.buyer = register_new_buyer(cls.buyer_id, cls.password)
        cls.buyer.add_funds(100000)
        cls._seed_sales()
        cls.url = urljoin(conf.URL, "search/recommend_by_tags")

    @classmethod
    def _add_books(cls):
        url = urljoin(conf.URL, "seller/add_book")
        headers = {"token": cls.seller.token}
        for entry in cls.books:
            bk = Book()
            bk.id = entry["book_id"]
            bk.title = entry["title"]
            bk.author = "Author"
            bk.publisher = "Publisher"
            bk.price = entry["price"]
            bk.tags = entry["tags"]
            bk.isbn = f"978{uuid.uuid4().hex[:9]}"
            bk.book_intro = entry["title"]
            bk.author_intro = "intro"
            bk.content = "content"
            payload = {
                "user_id": cls.seller_id,
                "store_id": cls.store_id,
                "book_info": bk.__dict__,
                "stock_level": 50,
            }
            resp = requests.post(url, headers=headers, json=payload)
            body = {}
            try:
                body = resp.json()
            except Exception:
                body = {"raw": resp.text}
            assert resp.status_code == 200, body

    @classmethod
    def _seed_sales(cls):
        # book0 sells 3 copies, book1 sells 1 copy, book2 none
        order_code, order_id = cls.buyer.new_order(
            cls.store_id, [(cls.books[0]["book_id"], 2)]
        )
        assert order_code == 200
        assert cls.buyer.payment(order_id) == 200

        order_code, order_id = cls.buyer.new_order(
            cls.store_id, [(cls.books[0]["book_id"], 1)]
        )
        assert order_code == 200
        assert cls.buyer.payment(order_id) == 200

        order_code, order_id = cls.buyer.new_order(
            cls.store_id, [(cls.books[1]["book_id"], 1)]
        )
        assert order_code == 200
        assert cls.buyer.payment(order_id) == 200

    def test_recommend_top_sold_first(self):
        payload = {
            "tags": ["悬疑"],
            "store_id": self.store_id,
            "limit": 5,
        }
        resp = requests.post(self.url, json=payload)
        data = resp.json()
        assert resp.status_code == 200, data
        books = data.get("books", [])
        assert len(books) >= 2
        top = books[0]
        second = books[1]
        assert top["book_id"] == self.books[0]["book_id"]
        assert second["book_id"] == self.books[1]["book_id"]
        assert "悬疑" in top["matched_tags"]
        assert top["sold_count"] >= second["sold_count"]

    def test_recommend_filters_by_tags(self):
        payload = {
            "tags": ["言情"],
            "store_id": self.store_id,
            "limit": 5,
        }
        resp = requests.post(self.url, json=payload)
        data = resp.json()
        assert resp.status_code == 200, data
        books = data.get("books", [])
        assert len(books) == 1
        assert books[0]["book_id"] == self.books[2]["book_id"]
        assert "言情" in books[0]["matched_tags"]
