import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def _get_database_url() -> str:
    url = os.getenv("BOOKSTORE_DB_URL")
    if not url:
        raise RuntimeError(
            "BOOKSTORE_DB_URL is not set. "
            "Please export e.g. mysql+pymysql://USER:PWD@HOST:PORT/bookstore"
        )
    return url



engine = create_engine(
    _get_database_url(),
    pool_pre_ping=True,
    future=True,
)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)
Base = declarative_base()


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
