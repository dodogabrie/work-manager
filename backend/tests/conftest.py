from __future__ import annotations

from datetime import date, timedelta

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


# ---------------------------------------------------------------- API (fase 4)

def _next_monday() -> date:
    """Lunedì futuro: orizzonte deterministico ma dentro la finestra della
    Manager View e del feed ICS, che sono ancorati a oggi reale."""
    today = date.today()
    return today + timedelta(days=(7 - today.weekday()) % 7 or 7)


API_MON = _next_monday()
OWNER_PASSWORD = "correct horse battery staple"


@pytest.fixture
def client(sessions, monkeypatch):
    from fastapi.testclient import TestClient

    from app.api import auth as auth_router
    from app.api.deps import today
    from app.config import settings
    from app.db import get_session
    from app.main import app
    from app.security import hash_password

    monkeypatch.setattr(settings, "owner_password_hash", hash_password(OWNER_PASSWORD))
    monkeypatch.setattr(settings, "enable_jobs", False)  # nessuno scheduler nei test
    # La suite non deve dipendere dal .env della macchina: con un
    # PUBLIC_BASE_URL in https il cookie diventa Secure e il TestClient, che
    # parla in http, non lo rimanda più indietro.
    monkeypatch.setattr(settings, "public_base_url", "http://testserver")
    monkeypatch.setattr(settings, "owner_password_hash_file", "")
    auth_router._attempts.clear()

    def override_session():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[today] = lambda: API_MON
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def owner(client):
    """Client già autenticato come owner."""
    response = client.post("/api/auth/login", json={"password": OWNER_PASSWORD})
    assert response.status_code == 200
    return client
