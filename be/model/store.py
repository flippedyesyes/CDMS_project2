import threading

from be.model.mongo import ensure_indexes

# global variable for database sync
init_completed_event = threading.Event()


def init_database(_db_path=None):
    """Ensure the MongoDB collection (and its indexes) is ready before serving."""
    ensure_indexes()
