"""API token per Claude: creati una volta, revocabili (§5.3, §28)."""

from __future__ import annotations

from app.models import ApiToken

from .conftest import OWNER_PASSWORD


def test_token_is_shown_once_and_stored_hashed(owner, session):
    created = owner.post("/api/tokens", json={"label": "claude", "scopes": ["plan"]}).json()

    assert created["token"]
    assert created["scopes"] == ["plan"]
    assert session.query(ApiToken).one().token_hash != created["token"]
    assert "token" not in owner.get("/api/tokens").json()[0]


def test_a_revoked_token_stops_working(owner, client):
    created = owner.post("/api/tokens", json={"label": "claude"}).json()
    headers = {"Authorization": f"Bearer {created['token']}"}
    owner.cookies.clear()
    assert client.get("/api/tasks", headers=headers).status_code == 200

    client.post("/api/auth/login", json={"password": OWNER_PASSWORD})
    assert client.delete(f"/api/tokens/{created['id']}").status_code == 200
    client.cookies.clear()

    assert client.get("/api/tasks", headers=headers).status_code == 401


def test_token_management_needs_the_owner(client):
    assert client.get("/api/tokens").status_code == 401
