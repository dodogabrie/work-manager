from __future__ import annotations

from datetime import date

import pytest

from app.models import (
    Action,
    PlanningSegment,
    PlanningSnapshot,
    ProposalKind,
    ProposalOrigin,
    ProposalStatus,
    TaskStatus,
)
from app.services import planning, proposals, tasks

from .conftest import MON

BEFORE_MON = date(2026, 1, 2)


def test_propose_never_touches_the_confirmed_plan(session):
    task = tasks.quick_add(session, "A", planning_effort_minutes=480)
    proposal = proposals.propose(
        session, ProposalKind.TASK_PLANNED, ProposalOrigin.API,
        {"tasks": {str(task.id): {"status": "PLANNED", "queue_position": "1000"}}},
        MON, originator="claude",
    )

    # §3.3: evento -> proposta -> simulazione. Niente è cambiato nel piano.
    assert proposal.status == ProposalStatus.PENDING
    assert proposal.base_plan_version == 0
    assert planning.plan_version(session) == 0
    assert session.query(PlanningSegment).count() == 0
    assert task.status == TaskStatus.INBOX
    assert proposal.simulation["segments"]  # la simulazione esiste comunque


def test_approve_writes_segments_snapshot_action_and_bumps_the_version(session):
    task = tasks.quick_add(session, "A", planning_effort_minutes=600)
    proposal = tasks.change_status(session, task.id, TaskStatus.PLANNED, horizon_start=MON)

    snapshot = proposals.approve(session, proposal.id)

    assert planning.plan_version(session) == 1
    assert snapshot.plan_version == 1
    assert task.status == TaskStatus.PLANNED
    assert [(s.day, s.minutes) for s in session.query(PlanningSegment).order_by("day")] == [
        (date(2026, 1, 5), 480), (date(2026, 1, 6), 120)
    ]
    action = session.query(Action).filter_by(action_type=str(ProposalKind.TASK_PLANNED)).one()
    assert action.snapshot_id == snapshot.id
    assert action.before["tasks"][str(task.id)]["status"] == "INBOX"
    assert proposal.status == ProposalStatus.APPLIED


def test_snapshot_is_a_complete_copy_not_a_diff(session):
    first = tasks.quick_add(session, "A", planning_effort_minutes=480)
    proposals.approve(
        session, tasks.change_status(session, first.id, TaskStatus.PLANNED, horizon_start=MON).id
    )
    second = tasks.quick_add(session, "B", planning_effort_minutes=480)
    snapshot = proposals.approve(
        session, tasks.change_status(session, second.id, TaskStatus.PLANNED, horizon_start=MON).id
    )

    payload = snapshot.payload
    # §22: lo snapshot contiene tutto il piano, non solo il task appena toccato.
    assert {t["title"] for t in payload["tasks"]} == {"A", "B"}
    assert len(payload["segments"]) == session.query(PlanningSegment).count() == 2
    assert payload["capacity"]["weekly"]["0"] == 480
    assert payload["plan_version"] == 2


def test_hard_conflict_blocks_approval(session):
    task = tasks.quick_add(
        session, "A", planning_effort_minutes=480, fixed_delivery_date=BEFORE_MON
    )
    proposal = tasks.change_status(session, task.id, TaskStatus.PLANNED, horizon_start=MON)

    assert proposal.simulation["conflicts"]  # §14.1
    with pytest.raises(proposals.HardConflictError):
        proposals.approve(session, proposal.id)
    assert planning.plan_version(session) == 0
    assert session.query(PlanningSegment).count() == 0


def test_warning_does_not_block_approval(session):
    task = tasks.quick_add(
        session, "A", planning_effort_minutes=480, target_delivery_date=BEFORE_MON
    )
    proposal = tasks.change_status(session, task.id, TaskStatus.PLANNED, horizon_start=MON)

    assert proposal.simulation["warnings"] and not proposal.simulation["conflicts"]  # §14.2
    proposals.approve(session, proposal.id)
    assert planning.plan_version(session) == 1


def test_reject_leaves_the_plan_untouched(session):
    task = tasks.quick_add(session, "A", planning_effort_minutes=480)
    proposal = tasks.change_status(session, task.id, TaskStatus.PLANNED, horizon_start=MON)

    proposals.reject(session, proposal.id)

    assert proposal.status == ProposalStatus.REJECTED
    assert planning.plan_version(session) == 0
    assert task.status == TaskStatus.INBOX
    with pytest.raises(proposals.ProposalNotPendingError):
        proposals.approve(session, proposal.id)


def test_approved_proposal_cannot_be_approved_twice(session):
    task = tasks.quick_add(session, "A", planning_effort_minutes=480)
    proposal = tasks.change_status(session, task.id, TaskStatus.PLANNED, horizon_start=MON)
    proposals.approve(session, proposal.id)

    with pytest.raises(proposals.ProposalNotPendingError):
        proposals.approve(session, proposal.id)
    assert session.query(PlanningSnapshot).count() == 1
