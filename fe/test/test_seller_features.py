import uuid

from fe.access.book import Book
from fe.access.new_seller import register_new_seller
from be.model.mongo import get_book_collection


def test_add_book_persists_search_fields():
    seller_id = f"seller_feature_{uuid.uuid4()}"
    store_id = f"store_feature_{uuid.uuid4()}"
    password = seller_id
    seller = register_new_seller(seller_id, password)
    assert seller.create_store(store_id) == 200

    book = Book()
    book.id = f"feature_book_{uuid.uuid4()}"
    book.title = "Feature Title"
    book.author = "Feature Author"
    book.book_intro = "Feature introduction"
    book.content = "Feature content"
    book.tags = ["feature", "test"]
    book.catalog = "Chapter 1\nChapter 2"

    assert seller.add_book(store_id, 3, book) == 200

    collection = get_book_collection()
    doc = collection.find_one(
        {"doc_type": "inventory", "store_id": store_id, "book_id": book.id},
        {"_id": 0, "title": 1, "search_text": 1, "tags": 1},
    )
    assert doc is not None
    assert doc.get("title") == book.title
    assert "Feature Title" in doc.get("search_text", "")
    assert doc.get("tags") == book.tags
