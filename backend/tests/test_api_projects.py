"""Progetti via API (§25, §32.4.6). Il rischio qui è che cancellare un progetto
porti via del lavoro pianificato."""

from __future__ import annotations

import uuid

from app.models import Task
from app.services.projects import DEFAULT_COLOR


def create(owner, name="MAG", **fields):
    response = owner.post("/api/projects", json={"name": name, **fields})
    assert response.status_code == 201, response.text
    return response.json()


def test_create_uses_a_default_color(owner):
    assert create(owner)["color"] == DEFAULT_COLOR
    assert create(owner, "Altro", color="#ff0000")["color"] == "#ff0000"


def test_create_rejects_an_empty_name(owner):
    assert owner.post("/api/projects", json={"name": "  "}).status_code == 400


def test_crud_round_trip(owner):
    project = create(owner, "  MAG  ")
    assert project["name"] == "MAG"

    patched = owner.patch(f"/api/projects/{project['id']}", json={"color": "#123456"})
    assert patched.status_code == 200
    assert patched.json() == {**project, "color": "#123456"}

    assert [p["id"] for p in owner.get("/api/projects").json()] == [project["id"]]


def test_unknown_project_is_404(owner):
    assert owner.get(f"/api/projects/{uuid.uuid4()}").status_code == 404


def test_archived_project_is_excluded_by_default(owner):
    live, archived = create(owner, "MAG"), create(owner, "Legacy")
    owner.patch(f"/api/projects/{archived['id']}", json={"archived": True})

    assert [p["id"] for p in owner.get("/api/projects").json()] == [live["id"]]
    everything = owner.get("/api/projects", params={"include_archived": True}).json()
    assert {p["id"] for p in everything} == {live["id"], archived["id"]}


def test_soft_delete_hides_the_project_but_keeps_the_task(owner, session):
    """§23.2: il progetto sparisce dalla lista, il task resta e continua a
    referenziarlo — un progetto cancellato non porta via del lavoro."""
    project = create(owner, "MAG")
    task = owner.post(
        "/api/inbox/quick-add", json={"title": "Fix import", "project_id": project["id"]}
    ).json()

    assert owner.delete(f"/api/projects/{project['id']}").status_code == 200

    assert owner.get("/api/projects").json() == []
    row = session.get(Task, uuid.UUID(task["id"]))
    assert row.deleted_at is None
    assert str(row.project_id) == project["id"]
    # resta leggibile per riga singola: la Manager View deve poter ancora
    # mostrare nome e colore del progetto di un task pianificato
    assert owner.get(f"/api/projects/{project['id']}").status_code == 200


def test_projects_require_authentication(client):
    assert client.get("/api/projects").status_code == 401
