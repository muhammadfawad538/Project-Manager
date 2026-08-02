# Line ending: LF
# Encoding: UTF-8

"""
SQLAlchemy session management for pmagent.

Usage:
    from pmagent.db.session import get_session, create_db

    create_db()                           # run once at startup
    with get_session() as session: ...    # use in request handlers / tools
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from pmagent.db.models import Base

_DEFAULT_DB_PATH = "data/app.db"


def _get_database_url() -> str:
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url
    # Default to SQLite file in data/ directory
    Path(_DEFAULT_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{_DEFAULT_DB_PATH}"


# Module-level engine — created once on import
_ENGINE = create_engine(
    _get_database_url(),
    connect_args={"check_same_thread": False},
    echo=False,
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_ENGINE)


def create_db() -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=_ENGINE)


@contextmanager
def get_session() -> Session:
    """Yield a database session. Use as a context manager: `with get_session() as s:`"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _get_database_url_public() -> str:
    """Public accessor for showing DB info in UI/logs (redacts password)."""
    return _get_database_url()
