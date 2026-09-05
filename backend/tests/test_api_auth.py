"""Autenticazione owner e token API (§5.1, §5.3, §28)."""

from __future__ import annotations

from app.api import auth as auth_router
from app.models import ApiToken
from app.security import generate_token, hash_token

from .conftest import OWNER_PASSWORD


def test_protected_endpoint_needs_authentication(client):
    assert client.get("/api/tasks").status_code == 401
    assert client.get("/api/planning").status_code == 401
    assert client.get("/api/auth/me").status_code == 401


def test_wrong_password_is_rejected(client):
    assert client.post("/api/auth/login", json={"password": "nope"}).status_code == 401


def test_login_sets_an_httponly_session_cookie(client):
    response = client.post("/api/auth/login", json={"password": OWNER_PASSWORD})

    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "httponly" in cookie.lower()
    assert "samesite=lax" in cookie.lower()
    assert client.get("/api/auth/me").json() == {"subject": "owner"}


def test_logout_clears_the_session(owner):
    owner.post("/api/auth/logout")
    assert owner.get("/api/auth/me").status_code == 401


def test_a_tampered_session_cookie_is_refused(client):
    client.cookies.set("wp_session", "forged")
    assert client.get("/api/auth/me").status_code == 401


def _issue(session, revoked_at=None) -> str:
    token = generate_token()
    session.add(ApiToken(label="claude", token_hash=hash_token(token), scopes=[],
                         revoked_at=revoked_at))
    session.commit()
    return token


def test_a_valid_api_token_grants_access(client, session):
    token = _issue(session)
    response = client.get("/api/tasks", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200


def test_api_token_last_used_is_recorded(client, session):
    token = _issue(session)
    client.get("/api/tasks", headers={"Authorization": f"Bearer {token}"})

    session.expire_all()
    row = session.query(ApiToken).one()
    assert row.last_used_at is not None


def test_a_revoked_api_token_is_refused(client, session):
    from datetime import UTC, datetime

    token = _issue(session, revoked_at=datetime.now(UTC))
    response = client.get("/api/tasks", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_an_unknown_api_token_is_refused(client):
    response = client.get("/api/tasks", headers={"Authorization": "Bearer whatever"})

    assert response.status_code == 401


def test_login_is_rate_limited(client):
    """§28: il brute force sulla password singola deve fermarsi presto."""
    codes = [
        client.post("/api/auth/login", json={"password": "nope"}).status_code
        for _ in range(auth_router.RATE_LIMIT + 2)
    ]

    assert codes[: auth_router.RATE_LIMIT] == [401] * auth_router.RATE_LIMIT
    assert codes[auth_router.RATE_LIMIT:] == [429, 429]
