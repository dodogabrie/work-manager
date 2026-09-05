"""Inbox, quick add e la regola per cui il piano non si tocca (§6.2, §3.3, §25)."""

from __future__ import annotations

import uuid

from app.models import PlanningSegment, Task, TaskStatus


def quick_add(owner, title="Fix MAG import", **fields):
    response = owner.post("/api/inbox/quick-add", json={"title": title, **fields})
    assert response.status_code == 201, response.text
    return response.json()


def test_quick_add_only_needs_a_title(owner):
    task = quick_add(owner, "  Fix MAG import  ")

    assert task["title"] == "Fix MAG import"
    assert task["status"] == TaskStatus.INBOX
    assert task["planning_effort_minutes"] == 0
    assert task["queue_position"] is None


def test_quick_add_rejects_an_empty_title(owner):
    assert owner.post("/api/inbox/quick-add", json={"title": "   "}).status_code == 400


def test_inbox_lists_only_unplanned_tasks(owner):
    quick_add(owner, "A")
    assert [t["title"] for t in owner.get("/api/inbox").json()] == ["A"]


def test_planning_a_task_returns_a_proposal_and_does_not_touch_the_plan(owner, session):
    """§3.3: l'intenzione produce una proposal, non segmenti."""
    task = quick_add(owner, "A", planning_effort_minutes=480)

    response = owner.post(f"/api/tasks/{task['id']}/status", json={"status": "PLANNED"})

    assert response.status_code == 200
    body = response.json()
    assert body["task"] is None
    assert body["proposal"]["status"] == "pending"
    assert body["proposal"]["simulation"]["segments"]
    assert session.query(PlanningSegment).count() == 0
    assert session.get(Task, uuid.UUID(task["id"])).status == TaskStatus.INBOX


def test_effort_change_returns_a_proposal(owner, session):
    task = quick_add(owner, "A", planning_effort_minutes=480)
    response = owner.post(f"/api/tasks/{task['id']}/effort/change", json={"minutes": 960})

    assert response.status_code == 200
    assert response.json()["kind"] == "EFFORT_CHANGE"
    assert session.query(PlanningSegment).count() == 0


def test_effort_proposal_only_stores_the_estimate(owner):
    """§15.1: la stima di Claude non è ancora il planning effort."""
    task = quick_add(owner, "A", planning_effort_minutes=480)
    body = owner.post(
        f"/api/tasks/{task['id']}/effort/propose",
        json={"minutes": 720, "min_minutes": 600, "max_minutes": 900,
              "confidence": "medium", "rationale": "conventional effort"},
    ).json()

    assert body["proposed_effort_minutes"] == 720
    assert body["planning_effort_minutes"] == 480


def test_patch_updates_a_task(owner):
    task = quick_add(owner, "A")
    body = owner.patch(f"/api/tasks/{task['id']}", json={"internal_notes": "private"}).json()

    assert body["internal_notes"] == "private"


def test_delete_is_a_soft_delete(owner):
    task = quick_add(owner, "A")
    assert owner.delete(f"/api/tasks/{task['id']}").status_code == 200
    assert owner.get(f"/api/tasks/{task['id']}").status_code == 404


def test_an_unknown_task_is_404(owner):
    assert owner.get("/api/tasks/00000000-0000-0000-0000-000000000000").status_code == 404


def approve_plan(owner, title, minutes=480):
    task = quick_add(owner, title, planning_effort_minutes=minutes)
    proposal = owner.post(
        f"/api/tasks/{task['id']}/status", json={"status": "PLANNED"}
    ).json()["proposal"]
    owner.post(f"/api/proposals/{proposal['id']}/approve")
    return task


def test_reordering_the_queue_is_only_an_intent(owner, session):
    """§14 / R9: il drag & drop simula, non applica."""
    first = approve_plan(owner, "A")
    second = approve_plan(owner, "B")
    before = [s.task_id for s in session.query(PlanningSegment).order_by(PlanningSegment.day)]

    response = owner.post(f"/api/tasks/{second['id']}/move", json={"after_id": first["id"]})

    assert response.status_code == 200
    assert response.json()["kind"] == "QUEUE_REORDER"
    session.expire_all()
    after = [s.task_id for s in session.query(PlanningSegment).order_by(PlanningSegment.day)]
    assert after == before


def test_completing_a_task_returns_a_proposal(owner):
    """§46.2: COMPLETED è esplicito e compatta in avanti."""
    task = approve_plan(owner, "A", 960)

    body = owner.post(f"/api/tasks/{task['id']}/complete", json={"actual_minutes": 300}).json()

    assert body["kind"] == "TASK_COMPLETED"
