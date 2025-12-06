from be.model.sql_conn import session_scope
from be.model.models import User, Inventory, Bookstore


class DBConn:
    """提供 SQLAlchemy session 的基类"""

    def __init__(self):
        self.session_scope = session_scope

    def user_id_exist(self, user_id: str) -> bool:
        with self.session_scope() as session:
            return session.get(User, user_id) is not None

    def book_id_exist(self, store_id: str, book_id: str) -> bool:
        with self.session_scope() as session:
            return (
                session.query(Inventory)
                .filter(
                    Inventory.store_id == store_id,
                    Inventory.book_id == book_id,
                )
                .first()
                is not None
            )

    def store_id_exist(self, store_id: str) -> bool:
        with self.session_scope() as session:
            return session.get(Bookstore, store_id) is not None
