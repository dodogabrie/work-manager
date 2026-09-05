from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base

MON = date(2026, 1, 5)  # lunedì, coerente con tests/helpers.py


@pytest.fixture
def engine():
    """SQLite in memoria condivisa: i service girano senza Docker."""
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def sessions(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def session(sessions):
    with sessions() as session:
        yield session
