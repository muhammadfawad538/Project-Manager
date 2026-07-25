# Line ending: LF
# Encoding: UTF-8

"""
Database session management and engine setup.

Usage:
    from pmagent.db.session import create_db, get_session, drop_db

    # First-run setup
    create_db()  # creates tables if they don't exist
    drop_db()    # drops all tables (destructive)

    # In application code
    with get_session() as session:
        ...
"""

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from pmagent.db.models import Base

# ---------------------------------------------------------------------------
# Engine / Session factory
# Default: SQLite file ``data/app.db`` under the project root.
# On Vercel / production: use DATABASE_URL env var (Postgres via Vercel Postgres).
# ---------------------------------------------------------------------------

_DEFAULT_DB_PATH = "sqlite:///data/app.db"


def _get_database_url() -> str:
    """Return the DB URL from env or the default SQLite path.

    Priority:
      1. DATABASE_URL env var (Postgres on Vercel, custom SQLite path, etc.)
      2. Default SQLite file at data/app.db
    """
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return url
    # Ensure data/ directory exists for SQLite
    db_path = "data/app.db"
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return f"sqlite:///{db_path}"


DATABASE_URL: str = _get_database_url()


def _engine_kwargs() -> dict:
    """Build engine kwargs based on the database dialect."""
    is_sqlite = DATABASE_URL.startswith("sqlite")
    return {
        "echo": False,  # set True for SQL debug logging
        "connect_args": {"check_same_thread": False} if is_sqlite else {},
        # Postgres connection pool settings for serverless (Vercel)
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }


engine = create_engine(DATABASE_URL, **_engine_kwargs())

# Auto-create tables on first engine use so callers don't have to remember create_db()
# Safe to call multiple times — idempotent.
Base.metadata.create_all(bind=engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_db() -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def drop_db() -> None:
    """Drop all tables.  **Destructive — use with care.**"""
    Base.metadata.drop_all(bind=engine)


def list_tables() -> list[str]:
    """Return a list of table names in the current DB."""
    return Base.metadata.tables.keys()


# ---------------------------------------------------------------------------
# Session context manager
# ---------------------------------------------------------------------------

@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Provide a transactional scope around a series of operations.

    Example:
        with get_session() as session:
            task = session.query(Task).first()
    """
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
