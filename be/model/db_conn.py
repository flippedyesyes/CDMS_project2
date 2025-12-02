from pymongo.collection import Collection

from be.model.mongo import get_book_collection


class DBConn:
    def __init__(self):
        self.collection: Collection = get_book_collection()

    def user_id_exist(self, user_id: str) -> bool:
        return (
            self.collection.find_one(
                {"doc_type": "user", "user_id": user_id}, {"_id": 1}
            )
            is not None
        )

    def book_id_exist(self, store_id: str, book_id: str) -> bool:
        return (
            self.collection.find_one(
                {
                    "doc_type": "inventory",
                    "store_id": store_id,
                    "book_id": book_id,
                },
                {"_id": 1},
            )
            is not None
        )

    def store_id_exist(self, store_id: str) -> bool:
        return (
            self.collection.find_one(
                {"doc_type": "store", "store_id": store_id}, {"_id": 1}
            )
            is not None
        )
