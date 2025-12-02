import uuid

from fe import conf
from fe.access.book import Book
from fe.access.new_seller import register_new_seller
from fe.access.search import Search as SearchClient


def make_book(keyword: str, suffix: str) -> Book:
    book = Book()
    book.id = f"{keyword}_{suffix}"
    book.title = f"{keyword} Title {suffix}"
    book.tags = [keyword, f"tag_{suffix}"]
    book.book_intro = f"Introduction about {keyword} #{suffix}"
    book.author = f"Author {suffix}"
    book.content = f"{keyword} content section {suffix}"
    book.catalog = f"{keyword} catalog item {suffix}"
    return book


class TestSearchBooks:
    def setup_method(self):
        self.keyword = f"kw_{uuid.uuid4().hex[:6]}"
        self.seller_id = f"seller_search_{uuid.uuid4()}"
        self.password = self.seller_id
        self.store_id = f"store_search_{uuid.uuid4()}"
        self.search_client = SearchClient(conf.URL)

        self.seller = register_new_seller(self.seller_id, self.password)
        assert self.seller.create_store(self.store_id) == 200

        self.other_seller_id = f"seller_other_{uuid.uuid4()}"
        self.other_store_id = f"store_other_{uuid.uuid4()}"
        self.other_seller = register_new_seller(
            self.other_seller_id, self.other_seller_id
        )
        assert self.other_seller.create_store(self.other_store_id) == 200

    def _add_book(self, seller_client, store_id: str, suffix: str):
        book = make_book(self.keyword, suffix)
        code = seller_client.add_book(store_id, 10, book)
        assert code == 200
        return book.id

    def test_search_keyword_global(self):
        book_a = self._add_book(self.seller, self.store_id, "global_a")
        book_b = self._add_book(self.other_seller, self.other_store_id, "global_b")

        status, data = self.search_client.books(self.keyword)
        assert status == 200
        ids = {item["book_id"] for item in data.get("books", [])}
        assert {book_a, book_b}.issubset(ids)
        assert data.get("total", 0) >= 2

    def test_search_store_scope(self):
        book_a = self._add_book(self.seller, self.store_id, "store_a")
        self._add_book(self.other_seller, self.other_store_id, "store_b")

        status, data = self.search_client.books(
            self.keyword, store_id=self.store_id, page=1, page_size=10
        )
        assert status == 200
        assert data.get("total") >= 1
        ids = {item["book_id"] for item in data.get("books", [])}
        assert book_a in ids
        assert all(item["store_id"] == self.store_id for item in data.get("books", []))

    def test_search_pagination(self):
        ids = [
            self._add_book(self.seller, self.store_id, f"page_{i}") for i in range(3)
        ]
        status, first_page = self.search_client.books(
            self.keyword, store_id=self.store_id, page=1, page_size=2
        )
        assert status == 200
        assert len(first_page.get("books", [])) == 2
        assert first_page.get("total") >= 3

        status, second_page = self.search_client.books(
            self.keyword, store_id=self.store_id, page=2, page_size=2
        )
        assert status == 200
        combined_ids = {
            *(item["book_id"] for item in first_page.get("books", [])),
            *(item["book_id"] for item in second_page.get("books", [])),
        }
        assert set(ids).issubset(combined_ids)
