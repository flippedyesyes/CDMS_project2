import pytest
import uuid

from fe import conf
from fe.access import book
from fe.access.new_seller import register_new_seller


class TestSellerBatchAdd:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.seller_id = f"seller_batch_{uuid.uuid4()}"
        self.store_id = f"store_batch_{uuid.uuid4()}"
        self.password = self.seller_id
        self.seller = register_new_seller(self.seller_id, self.password)
        assert self.seller.create_store(self.store_id) == 200
        book_db = book.BookDB(conf.Use_Large_DB)
        self.books = book_db.get_book_info(0, 3)
        yield

    def _payload(self, books):
        data = []
        for bk in books:
            data.append({"book_info": bk.__dict__, "stock_level": 5})
        return data

    def test_batch_add_ok(self):
        payload = self._payload(self.books)
        code, resp = self.seller.batch_add_books(self.store_id, payload)
        assert code == 200
        results = resp.get("results", [])
        assert len(results) == len(payload)
        assert all(item["code"] == 200 for item in results)

    def test_batch_add_partial_failure(self):
        # Insert one book beforehand to trigger duplicate error.
        first = self.books[0]
        assert self.seller.add_book(self.store_id, 5, first) == 200
        payload = self._payload(self.books[:2])
        code, resp = self.seller.batch_add_books(self.store_id, payload)
        assert code == 200
        results = resp.get("results", [])
        assert len(results) == 2
        has_failure = any(item["code"] != 200 for item in results)
        assert has_failure

    def test_batch_add_invalid_store(self):
        payload = self._payload(self.books[:1])
        code, _ = self.seller.batch_add_books(self.store_id + "_invalid", payload)
        assert code != 200
