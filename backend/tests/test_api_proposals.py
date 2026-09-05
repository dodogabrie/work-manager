"""Approvazione: transazionalità, staleness e conflitti hard (§12.1, §14.1, §26)."""

from __future__ import annotations

from .conftest import API_MON


def plan_proposal(owner, title="A", minutes=480, **fields):
    task = owner.post(
        "/api/inbox/quick-add",
        json={"title": title, "planning_effort_minutes": minutes, **fields},
    ).json()
    body = owner.post(f"/api/tasks/{task['id']}/status", json={"status": "PLANNED"}).json()
    return task, body["proposal"]


def plan_version(owner) -> int:
    return owner.get("/api/planning").json()["plan_version"]


def test_approve_applies_the_plan_and_bumps_the_version(owner):
    before = plan_version(owner)
    _, proposal = plan_proposal(owner)

    response = owner.post(f"/api/proposals/{proposal['id']}/approve")

    assert response.status_code == 200
    assert response.json()["plan_version"] == before + 1
    assert plan_version(owner) == before + 1
    assert owner.get("/api/planning").json()["segments"]


def test_a_stale_proposal_is_a_conflict(owner):
    """§12.1: calcolata su una versione del piano non più corrente -> 409."""
    _, first = plan_proposal(owner, "A")
    _, second = plan_proposal(owner, "B")

    assert owner.post(f"/api/proposals/{first['id']}/approve").status_code == 200
    response = owner.post(f"/api/proposals/{second['id']}/approve")

    assert response.status_code == 409
    assert "v0" in response.json()["detail"] or "plan v" in response.json()["detail"]
    assert owner.get(f"/api/proposals/{second['id']}").json()["status"] == "stale"


def test_a_stale_proposal_can_be_recalculated_then_approved(owner):
    _, first = plan_proposal(owner, "A")
    _, second = plan_proposal(owner, "B")
    owner.post(f"/api/proposals/{first['id']}/approve")
    owner.post(f"/api/proposals/{second['id']}/approve")

    recalculated = owner.post(f"/api/proposals/{second['id']}/recalculate")

    assert recalculated.status_code == 200
    assert recalculated.json()["status"] == "pending"
    assert owner.post(f"/api/proposals/{second['id']}/approve").status_code == 200


def test_a_hard_conflict_blocks_the_approval(owner):
    """§14.1 / R8: una fixed date irraggiungibile non è confermabile -> 422."""
    _, proposal = plan_proposal(
        owner, "Release", minutes=16 * 60, fixed_delivery_date=API_MON.isoformat()
    )

    assert proposal["simulation"]["conflicts"]
    response = owner.post(f"/api/proposals/{proposal['id']}/approve")

    assert response.status_code == 422
    assert "fixed" in response.json()["detail"].lower()


def test_reject_closes_the_proposal(owner):
    _, proposal = plan_proposal(owner)

    assert owner.post(f"/api/proposals/{proposal['id']}/reject").json()["status"] == "rejected"
    assert owner.post(f"/api/proposals/{proposal['id']}/approve").status_code == 409


def test_pending_proposals_are_listed(owner):
    plan_proposal(owner, "A")
    listed = owner.get("/api/proposals", params={"status": "pending"}).json()

    assert [p["kind"] for p in listed] == ["TASK_PLANNED"]


def test_an_unknown_proposal_is_404(owner):
    assert owner.get("/api/proposals/00000000-0000-0000-0000-000000000000").status_code == 404
