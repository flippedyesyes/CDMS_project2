import os
import threading

from be.model.mongo import ensure_indexes
from be.model.sql_conn import Base, engine

# global variable for database sync
init_completed_event = threading.Event()


def init_database(_db_path=None):
    """Ensure MongoDB indexes and SQL tables are initialized."""
    ensure_indexes()
    if os.getenv("BOOKSTORE_RESET_DB") == "1":
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
