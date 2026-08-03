# Line ending: LF
# Encoding: UTF-8

"""
Database test fixtures for pmagent.

Uses an in-memory SQLite database so tests don't touch the real data/app.db.
Tables are recreated fresh for each test via the isolate_db autouse fixture.
"""

from __future__ import annotations

import pytest
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from pmagent.db.models import Base


# In-memory test engine — isolated from the real database
_TEST_ENGINE = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
_TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_TEST_ENGINE)


def _create_schema() -> None:
    Base.metadata.drop_all(bind=_TEST_ENGINE)
    Base.metadata.create_all(bind=_TEST_ENGINE)


@contextmanager
def _test_get_session():
    """Context manager that yields a fresh test session."""
    session = _TestSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture(autouse=True)
def isolate_db():
    """Reset the in-memory DB before each test and patch all session references.

    Tests that receive the `db` fixture use it directly.
    Tests that call `get_session()` get the test engine because we monkeypatch
    the session module here.
    """
    import pmagent.db.session as session_mod
    import pmagent.db.repository as repo_mod

    _create_schema()
    # Patch the module-level engine and SessionLocal
    session_mod._ENGINE = _TEST_ENGINE
    session_mod.SessionLocal = _TestSessionLocal
    # Patch the context manager used by tools and API routes
    session_mod.get_session = _test_get_session
    repo_mod.get_session = _test_get_session
    yield
    # No teardown needed — in-memory DB disappears with the engine


@pytest.fixture()
def db():
    """Provide a raw session for tests that need direct DB access.

    Use this inside the `with` block and extract IDs before the block exits.
    """
    session = _TestSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
