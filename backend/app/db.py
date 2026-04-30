#read only db session
"""
Database access for the tool layer.

The engine is created once and shared. Every tool that needs SQL access
goes through `read_only_session()`, which opens a transaction in
PostgreSQL READ ONLY mode. Even if a tool somehow constructed an INSERT,
UPDATE, or DELETE, the database itself would refuse it.
"""

import os
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

load_dotenv()

_engine = create_engine(
    os.environ["DATABASE_URL"],
    pool_pre_ping=True,   # validate connections before use
    pool_size=5,
    max_overflow=2,
    future=True,
)

_SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)


@contextmanager
def read_only_session() -> Session:
    """Yield a session that cannot mutate the database.

    Postgres enforces this server-side via SET TRANSACTION READ ONLY.
    Any write attempt raises an error from the database itself, not from
    application code that could be bypassed.
    """
    session = _SessionFactory()
    try:
        session.execute(text("SET TRANSACTION READ ONLY"))
        yield session
    finally:
        session.close()


def get_engine():
    """For schema introspection or one-off use. Prefer read_only_session()."""
    return _engine