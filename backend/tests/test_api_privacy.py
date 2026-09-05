"""Privacy per campo della Manager View (§5.2, §27).

Il test è volutamente paranoico: guarda il corpo grezzo della risposta, non i
campi del DTO. Se un domani qualcuno serializzasse il modello Task, qui si rompe.
"""

from __future__ import annotations

import pytest

from app.models import TaskStatus
from app.schemas import PUBLIC_STATUS, TaskClaudeView, TaskInternalView

from .conftest import OWNER_PASSWORD

#: Campi che non devono mai lasciare l'owner application (§5.2, §27).
OWNER_ONLY_FIELDS = (
    "internal_notes",
    "ready_at",
    "delivered_at",
    "completed_at",
    "proposed_effort_minutes",
    "proposed_effort_min_minutes",
    "proposed_effort_max_minutes",
    "estimate_confidence",
    "estimate_rationale",
    "queue_position",
    "description",
    "token",
    "token_hash",
)

SECRETS = {
    "internal_notes": "il manager non deve leggere questo",
    "estimate_rationale": "stima interna, non condivisibile",
    "description": "dettaglio tecnico interno",
}


@pytest.fixture
def shared(owner):
    """Un task pianificato, approvato, portato a READY, e un link manager attivo."""
    task = owner.post("/api/inbox/quick-add", json={
        "title": "Fix MAG import",
        "planning_effort_minutes": 300,
        **SECRETS,
    }).json()
    owner.post(f"/api/tasks/{task['id']}/effort/propose", json={
        "minutes": 420, "min_minutes": 360, "max_minutes": 480,
        "confidence": "low", "rationale": SECRETS["estimate_rationale"],
    })
    proposal = owner.post(
        f"/api/tasks/{task['id']}/status", json={"status": "PLANNED"}
    ).json()["proposal"]
    owner.post(f"/api/proposals/{proposal['id']}/approve")
    owner.post(f"/api/tasks/{task['id']}/status", json={"status": "IN_PROGRESS"})
    # §3.2: READY è interno — il piano non cambia e il manager non deve vederlo.
    assert owner.post(
        f"/api/tasks/{task['id']}/status", json={"status": "READY"}
    ).json()["task"]["status"] == "READY"

    link = owner.post("/api/share-links", json={"label": "manager", "kind": "manager"}).json()
    # La Manager View è una superficie pubblica: si guarda senza sessione owner.
    owner.cookies.clear()
    return task, link["token"]


def test_manager_view_never_exposes_owner_only_fields(client, shared):
    _, token = shared

    response = client.get(f"/api/share/{token}/planning")

    assert response.status_code == 200
    body = response.text
    payload = response.json()
    assert payload, "il piano condiviso non deve essere vuoto"
    for field in OWNER_ONLY_FIELDS:
        assert field not in body, f"{field} è owner-only (§27)"
    for secret in SECRETS.values():
        assert secret not in body


def test_manager_view_hides_the_internal_ready_status(client, shared):
    """§5.2: lo stato READY non deve trapelare, nemmeno come stringa."""
    _, token = shared

    response = client.get(f"/api/share/{token}/planning")

    assert "READY" not in response.text
    assert response.json()[0]["status"] == "IN_PROGRESS"


def test_manager_view_shows_what_it_is_supposed_to(client, shared):
    _, token = shared

    task = client.get(f"/api/share/{token}/planning").json()[0]

    assert task["title"] == "Fix MAG import"
    assert task["planned_effort_minutes"] == 300
    assert task["allocation_start"] and task["allocation_end"]
    assert task["delivery_date"]


def test_manager_view_needs_no_session(client, shared):
    """§5.2: il link funziona senza account — ma solo quel link."""
    _, token = shared
    assert client.get(f"/api/share/{token}/planning").status_code == 200
    assert client.get("/api/tasks").status_code == 401


def test_ready_is_never_a_public_status():
    assert TaskStatus.READY not in PUBLIC_STATUS.values()
    assert PUBLIC_STATUS[TaskStatus.READY] == "IN_PROGRESS"


def test_the_claude_view_drops_private_notes_only():
    """§27: Claude vede tutto tranne le note interne."""
    assert "internal_notes" in TaskInternalView.model_fields
    assert "internal_notes" not in TaskClaudeView.model_fields
    assert "estimate_rationale" in TaskClaudeView.model_fields


def test_the_owner_does_see_the_private_notes(client, shared):
    task, _ = shared
    client.post("/api/auth/login", json={"password": OWNER_PASSWORD})

    body = client.get(f"/api/tasks/{task['id']}").json()

    assert body["internal_notes"] == SECRETS["internal_notes"]


def test_api_token_client_does_not_receive_internal_notes(client, session, shared):
    from app.models import ApiToken
    from app.security import generate_token, hash_token

    task, _ = shared
    token = generate_token()
    session.add(ApiToken(label="claude", token_hash=hash_token(token), scopes=[]))
    session.commit()

    body = client.get(
        f"/api/tasks/{task['id']}", headers={"Authorization": f"Bearer {token}"}
    ).json()

    assert "internal_notes" not in body
    assert body["estimate_rationale"] == SECRETS["estimate_rationale"]
