"""Share link e feed ICS: revoca, scadenza, sottoscrivibilità (§5.2, §18, §28)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models import ManagerShareLink


def make_link(owner, kind="manager", expires_at=None):
    payload = {"label": f"{kind} link", "kind": kind}
    if expires_at is not None:
        payload["expires_at"] = expires_at.isoformat()
    response = owner.post("/api/share-links", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def plan_something(owner):
    task = owner.post("/api/inbox/quick-add", json={
        "title": "RAW processing API", "planning_effort_minutes": 720
    }).json()
    proposal = owner.post(
        f"/api/tasks/{task['id']}/status", json={"status": "PLANNED"}
    ).json()["proposal"]
    owner.post(f"/api/proposals/{proposal['id']}/approve")
    return task


def test_the_token_is_shown_once_and_stored_hashed(owner, session):
    link = make_link(owner)

    assert link["token"]
    assert link["url"].endswith(f"/share/{link['token']}")
    row = session.query(ManagerShareLink).one()
    assert link["token"] not in row.token_hash
    assert "token" not in owner.get("/api/share-links").json()[0]


def test_a_revoked_link_is_not_found(owner):
    link = make_link(owner)
    assert owner.delete(f"/api/share-links/{link['id']}").status_code == 200
    owner.cookies.clear()

    assert owner.get(f"/api/share/{link['token']}/planning").status_code == 404


def test_an_expired_link_is_not_found(owner):
    link = make_link(owner, expires_at=datetime.now(UTC) - timedelta(minutes=1))
    owner.cookies.clear()

    assert owner.get(f"/api/share/{link['token']}/planning").status_code == 404


def test_a_link_expiring_later_still_works(owner):
    link = make_link(owner, expires_at=datetime.now(UTC) + timedelta(days=1))
    owner.cookies.clear()

    assert owner.get(f"/api/share/{link['token']}/planning").status_code == 200


def test_an_unknown_token_is_not_found(client):
    assert client.get("/api/share/nope/planning").status_code == 404


def test_a_manager_token_does_not_open_the_calendar_feed(owner):
    """I due tipi di link sono separati: uno non vale per l'altro."""
    link = make_link(owner, kind="manager")
    owner.cookies.clear()

    assert owner.get(f"/calendar/{link['token']}.ics").status_code == 404


def test_the_ics_token_serves_a_subscribable_calendar(owner):
    """§18: nessuna sessione, così Outlook può sottoscriverlo."""
    plan_something(owner)
    link = make_link(owner, kind="ics")
    assert link["url"].endswith(f"/calendar/{link['token']}.ics")
    owner.cookies.clear()

    response = owner.get(f"/calendar/{link['token']}.ics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    body = response.text
    assert body.startswith("BEGIN:VCALENDAR")
    assert "END:VCALENDAR" in body
    assert "RAW processing API" in body
    assert body.count("BEGIN:VEVENT") == 2  # 12h = due giornate, un evento per segmento


def test_the_feed_records_the_access(owner, session):
    link = make_link(owner, kind="ics")
    owner.cookies.clear()
    owner.get(f"/calendar/{link['token']}.ics")

    session.expire_all()
    assert session.query(ManagerShareLink).one().last_accessed_at is not None


def test_share_link_management_needs_the_owner(client):
    assert client.get("/api/share-links").status_code == 401
    assert client.post("/api/share-links", json={"label": "x"}).status_code == 401
