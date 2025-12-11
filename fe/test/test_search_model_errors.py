import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from be.model.search import Search
from script.doubao_client import DoubaoError


def test_get_cached_ocr_missing_file(monkeypatch):
    monkeypatch.setenv("BOOKSTORE_OCR_CACHE", str(Path("nonexistent.json")))
    s = Search()
    assert s._get_cached_ocr("path") is None


def test_get_cached_ocr_invalid_file(monkeypatch):
    with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
        tmp.write("not json")
        tmp_path = tmp.name
    monkeypatch.setenv("BOOKSTORE_OCR_CACHE", tmp_path)
    try:
        s = Search()
        assert s._get_cached_ocr("path") is None
    finally:
        os.remove(tmp_path)


def test_search_books_by_image_missing_path():
    s = Search()
    code, _, _ = s.search_books_by_image("", None, 10)
    assert code == 400


def test_search_books_by_image_ocr_failure(monkeypatch):
    with tempfile.NamedTemporaryFile("w", suffix=".jpg", delete=False) as tmp:
        path = tmp.name
    try:
        s = Search()
        monkeypatch.setattr(s, "_get_cached_ocr", lambda _: None)
        monkeypatch.setenv("BOOKSTORE_OCR_CACHE", "")

        def fake_ocr(_):
            raise DoubaoError("fail")

        monkeypatch.setattr("be.model.search.recognize_image_text", fake_ocr)
        code, msg, _ = s.search_books_by_image(path, None, 10)
        assert code == 530
        assert "OCR failed" in msg
    finally:
        os.remove(path)


def test_search_books_by_image_empty_keywords(monkeypatch):
    with tempfile.NamedTemporaryFile("w", suffix=".jpg", delete=False) as tmp:
        path = tmp.name
    try:
        s = Search()
        monkeypatch.setattr(s, "_get_cached_ocr", lambda _: None)
        monkeypatch.setenv("BOOKSTORE_OCR_CACHE", "")
        monkeypatch.setattr("be.model.search.recognize_image_text", lambda path: "\n\n")
        code, _, payload = s.search_books_by_image(path, None, 10)
        assert code == 404
        assert payload["recognized_text"] == ""
    finally:
        os.remove(path)


def test_search_books_by_image_target_book_fallback(monkeypatch):
    s = Search()
    # Prepare fake search result returns nothing
    monkeypatch.setattr(s, "search_books", lambda *args, **kwargs: (200, "ok", {"books": []}))

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def query(self, *args, **kwargs):
            class FakeQuery:
                def join(self, *args, **kwargs):
                    return self

                def filter(self, *args, **kwargs):
                    return self

                def all(self_non):
                    inv = SimpleNamespace(
                        store_id="store",
                        book_id="target",
                        stock_level=1,
                        book_info=json.dumps({"title": "fallback"}),
                    )
                    book = SimpleNamespace(book_id="target")
                    return [(inv, book)]

            return FakeQuery()

    monkeypatch.setattr(s, "session_scope", lambda: FakeSession())
    payload_text = "keyword"
    code, msg, payload = s.search_books_by_image(
        image_path="fake.jpg",
        store_id=None,
        page_size=5,
        override_text=payload_text,
        override_book_id="target",
    )
    assert code == 200
    assert payload["books"][0]["matched_keyword"] == "cached"


def test_recommend_by_tags_empty_tags():
    s = Search()
    code, msg, _ = s.recommend_by_tags([], None, 10)
    assert code == 400
    assert msg == "tags are required"
