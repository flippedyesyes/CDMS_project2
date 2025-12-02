from unittest.mock import patch

import pytest
from pymongo.errors import OperationFailure

from be.model import mongo as mongo_mod


@pytest.fixture
def collection():
    # Ensure each test operates on a fresh index initialization path.
    mongo_mod._indexes_ready = False
    return mongo_mod.get_book_collection()


def test_ensure_indexes_populates_new_indexes(collection):
    mongo_mod._indexes_ready = False
    mongo_mod.ensure_indexes()
    info = collection.index_information()
    assert "idx_order_status_expire" in info
    assert "idx_inventory_search_text" in info or info.get("book_fulltext")


def test_ensure_indexes_handles_existing_text_index(collection):
    original_create = collection.create_index

    def side_effect(*args, **kwargs):
        name = kwargs.get("name")
        if name == "idx_inventory_search_text":
            raise OperationFailure("existing text index", code=67)
        return original_create(*args, **kwargs)

    mongo_mod._indexes_ready = False
    with patch.object(collection, "create_index", side_effect=side_effect):
        mongo_mod.ensure_indexes()
    info = collection.index_information()
    assert "idx_order_status_expire" in info

