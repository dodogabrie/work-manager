"""Piano, contesto per Claude, simulazione, capacità, history (§13, §16.1, §11, §23)."""

from __future__ import annotations

from datetime import timedelta

from app.models import PlanningSegment

from .conftest import API_MON


def plan(owner, title="A", minutes=480, **fields):
    task = owner.post("/api/inbox/quick-add", json={
        "title": title, "planning_effort_minutes": minutes, **fields
    }).json()
    proposal = owner.post(
        f"/api/tasks/{task['id']}/status", json={"status": "PLANNED"}
    ).json()["proposal"]
    owner.post(f"/api/proposals/{proposal['id']}/approve")
    return task


def test_planning_returns_segments_days_and_tasks(owner):
    plan(owner, "A", 720)

    body = owner.get("/api/planning").json()

    assert body["plan_version"] == 1
    assert [t["title"] for t in body["tasks"]] == ["A"]
    assert [s["minutes"] for s in body["segments"]] == [480, 240]
    monday = next(d for d in body["days"] if d["day"] == API_MON.isoformat())
    assert monday == {"day": API_MON.isoformat(), "available_minutes": 480,
                      "planned_minutes": 480}


def test_context_is_compact_and_carries_the_constraints(owner):
    plan(owner, "planned")
    owner.post("/api/inbox/quick-add", json={"title": "inbox only"})

    body = owner.get("/api/planning/context").json()

    assert body["today"] == API_MON.isoformat()
    assert [t["title"] for t in body["inbox"]] == ["inbox only"]
    assert [t["title"] for t in body["queue"]] == ["planned"]
    assert body["segments"] and body["capacity"]
    assert body["pending_proposals"] == []
    assert any("coda" in c for c in body["constraints"])
    # §27: nemmeno il contesto per Claude porta le note private.
    assert "internal_notes" not in body["inbox"][0]


def test_simulate_does_not_touch_the_plan(owner, session):
    """§13: stessa semantica della preview, senza creare proposal né segmenti."""
    task = plan(owner, "A", 480)
    before = session.query(PlanningSegment).count()

    body = owner.post("/api/planning/simulate", json={
        "tasks": {task["id"]: {"planning_effort_minutes": 960}}
    }).json()

    assert sum(s["minutes"] for s in body["segments"]) == 960
    assert body["changes"]
    assert session.query(PlanningSegment).count() == before
    assert owner.get("/api/proposals", params={"status": "pending"}).json() == []


def test_capacity_exception_without_a_plan_is_applied_directly(owner):
    """§11.3: se non c'è nulla da spostare non serve una proposal."""
    body = owner.post("/api/capacity/exceptions", json={
        "day": API_MON.isoformat(), "minutes": 240, "kind": "LEAVE", "note": "permesso"
    }).json()

    assert body["proposal"] is None
    assert body["exception"]["minutes"] == 240
    capacity = owner.get("/api/capacity").json()
    assert capacity["weekly_minutes"]["0"] == 480
    assert [e["note"] for e in capacity["exceptions"]] == ["permesso"]
    assert capacity["days"][0]["available_minutes"] == 240


def test_capacity_exception_over_a_plan_returns_a_proposal(owner):
    """§11.3 / §36: ferie su un piano esistente -> proposal, non applicazione."""
    plan(owner, "A", 480)

    body = owner.post("/api/capacity/exceptions", json={
        "day": API_MON.isoformat(), "minutes": 0, "kind": "VACATION"
    }).json()

    assert body["exception"] is None
    assert body["proposal"]["kind"] == "CAPACITY_CHANGE"
    assert owner.get("/api/capacity").json()["days"][0]["available_minutes"] == 480


def test_capacity_exception_can_be_deleted(owner):
    created = owner.post("/api/capacity/exceptions", json={
        "day": (API_MON + timedelta(days=1)).isoformat(), "minutes": 0
    }).json()["exception"]

    assert owner.delete(f"/api/capacity/exceptions/{created['id']}").status_code == 200
    assert owner.get("/api/capacity").json()["exceptions"] == []


def test_approving_records_a_snapshot_and_an_action(owner):
    plan(owner, "A")

    snapshots = owner.get("/api/snapshots").json()
    actions = owner.get("/api/actions").json()

    assert [s["plan_version"] for s in snapshots] == [1]
    assert owner.get(f"/api/snapshots/{snapshots[0]['id']}").json()["payload"]["tasks"]
    assert actions[0]["action_type"] == "TASK_PLANNED"
    assert actions[0]["reversible"] is True


def test_undo_of_a_plan_action_proposes_instead_of_applying(owner):
    """§23.3: l'undo che tocca il piano passa dal flusso di approvazione."""
    plan(owner, "A")
    action = owner.get("/api/actions").json()[0]

    body = owner.post(f"/api/actions/{action['id']}/undo").json()

    assert body["status"] == "proposal"
    assert body["proposal"]["kind"] == "UNDO"
    assert owner.get("/api/planning").json()["plan_version"] == 1

    assert owner.post(f"/api/proposals/{body['proposal']['id']}/approve").status_code == 200
    assert owner.get("/api/planning").json()["segments"] == []


def test_undo_of_an_unknown_action_is_impossible(owner):
    body = owner.post(
        "/api/actions/00000000-0000-0000-0000-000000000000/undo"
    ).json()

    assert body["status"] == "impossible"
