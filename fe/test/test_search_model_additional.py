import contextlib
import json
from types import SimpleNamespace

from be.model import search as search_module
from be.model.dao import search_dao


def dummy_session_scope():
    @contextlib.contextmanager
    def _scope():
        yield SimpleNamespace()

    return _scope


def test_search_books_invalid_json(monkeypatch):
    captured = {}

    def fake_search(session, **kwargs):
        captured.update(kwargs)
        inv = SimpleNamespace(store_id="store", stock_level=5, book_info="not json")
        book = SimpleNamespace(book_id="book1")
        return 1, [{"inventory": inv, "book": book}]

    monkeypatch.setattr(search_dao, "search_books", fake_search)
    s = search_module.Search()
    s.session_scope = dummy_session_scope()

    code, msg, payload = s.search_books("keyword", "store-x", page=-1, page_size=200)
    assert code == 200
    assert payload["page"] == 1
    assert payload["page_size"] == 50
    assert payload["books"][0]["book_info"] == {}
    assert captured["store_id"] == "store-x"


def test_recommend_by_tags_success(monkeypatch):
    def fake_recommend(session, tags, store_id, limit):
        inv = SimpleNamespace(
            store_id=store_id or "store", book_id="book2", stock_level=3, book_info="{}"
        )
        return [{"inventory": inv, "matched_tags": tags, "sold_count": 5}]

    monkeypatch.setattr(search_dao, "recommend_by_tags", fake_recommend)
    s = search_module.Search()
    s.session_scope = dummy_session_scope()

    code, msg, payload = s.recommend_by_tags(["tag1", "tag2"], "store-1", limit=5)
    assert code == 200
    assert payload["tags"] == ["tag1", "tag2"]
    assert payload["books"][0]["matched_tags"] == ["tag1", "tag2"]


def test_search_books_default_pagination(monkeypatch):
    captured = {}

    def fake_search(session, **kwargs):
        captured.update(kwargs)
        inv = SimpleNamespace(store_id="store", stock_level=1, book_info="{}")
        book = SimpleNamespace(book_id="book-default")
        return 0, [{"inventory": inv, "book": book}]

    monkeypatch.setattr(search_dao, "search_books", fake_search)
    s = search_module.Search()
    s.session_scope = dummy_session_scope()

    code, _, payload = s.search_books(None, None, page=None, page_size=None)
    assert code == 200
    assert payload["page"] == 1
    assert payload["page_size"] == 20
    assert captured["page"] == 1
    assert captured["page_size"] == 20


def test_search_books_by_image_override_text(monkeypatch):
    s = search_module.Search()
    s.session_scope = dummy_session_scope()

    def fake_search(self, keyword, store_id, page, page_size):
        return 200, "ok", {
            "books": [
                {
                    "book_id": f"{keyword}-id",
                    "store_id": "store",
                    "stock_level": 1,
                    "book_info": {"title": keyword},
                }
            ]
        }

    monkeypatch.setattr(search_module.Search, "search_books", fake_search)

    code, msg, payload = s.search_books_by_image(
        image_path="unused",
        store_id=None,
        page_size=5,
        override_text="Hello\nWorld\n",
    )
    assert code == 200
    assert payload["recognized_text"].splitlines()[0] == "Hello"
    book_ids = {book["book_id"] for book in payload["books"]}
    assert book_ids == {"Hello-id", "World-id"}


def test_search_books_by_image_cache_hit(monkeypatch, tmp_path):
    cache_file = tmp_path / "cache.json"
    cache_file.write_text(
        json.dumps(
            [
                {
                    "image_path": "img.jpg",
                    "ocr_text": "cached-key",
                    "book_id": "cached-book",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BOOKSTORE_OCR_CACHE", str(cache_file))
    s = search_module.Search()
    s.session_scope = dummy_session_scope()

    monkeypatch.setattr(
        search_module.Search,
        "search_books",
        lambda self, keyword, store_id, page, page_size: (200, "ok", {"books": []}),
    )

    rows = [
        (
            SimpleNamespace(
                store_id="store",
                book_id="cached-book",
                stock_level=1,
                book_info=json.dumps({"title": "cached"}),
            ),
            SimpleNamespace(book_id="cached-book"),
        )
    ]

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

        def query(self, *args, **kwargs):
            class FakeQuery:
                def join(self, *args, **kwargs):
                    return self

                def filter(self, *args, **kwargs):
                    return self

                def all(self):
                    return rows

            return FakeQuery()

    s.session_scope = lambda: FakeSession()
    code, msg, payload = s.search_books_by_image("img.jpg", None, page_size=5)
    assert code == 200
    assert payload["books"][0]["matched_keyword"] == "cached"


def test_search_books_error_path(monkeypatch):
    s = search_module.Search()
    s.session_scope = dummy_session_scope()

    def raise_exc(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(search_dao, "search_books", raise_exc)
    code, msg, payload = s.search_books("kw", None, page=1, page_size=10)
    assert code == 530
    assert payload == {}


def test_recommend_by_tags_limit_clamp(monkeypatch):
    s = search_module.Search()
    s.session_scope = dummy_session_scope()

    def fake_recommend(session, tags, store_id, limit):
        assert limit == 50
        inv = SimpleNamespace(
            store_id="store", book_id="book", stock_level=1, book_info="{}"
        )
        return [{"inventory": inv, "matched_tags": tags}]

    monkeypatch.setattr(search_dao, "recommend_by_tags", fake_recommend)
    code, msg, payload = s.recommend_by_tags(["a"], None, limit=5000)
    assert code == 200
    assert payload["books"][0]["matched_tags"] == ["a"]
