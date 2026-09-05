from __future__ import annotations

from decimal import Decimal

import pytest

from app.models import Action, PlanningProposal, PlanningSegment, Task, TaskStatus
from app.services import proposals, tasks

from .conftest import MON


def plan(session, title="T", minutes=480):
    task = tasks.quick_add(session, title, planning_effort_minutes=minutes)
    proposal = tasks.change_status(session, task.id, TaskStatus.PLANNED, horizon_start=MON)
    proposals.approve(session, proposal.id)
    return task


def test_quick_add_only_needs_a_title(session):
    task = tasks.quick_add(session, "  Fix the invoice export  ")
    assert task.title == "Fix the invoice export"
    assert task.status == TaskStatus.INBOX
    assert task.planning_effort_minutes == 0
    assert task.queue_position is None


def test_quick_add_rejects_an_empty_title(session):
    with pytest.raises(ValueError):
        tasks.quick_add(session, "   ")


def test_inbox_to_planned_returns_a_proposal_and_changes_nothing(session):
    task = tasks.quick_add(session, "A", planning_effort_minutes=480)
    result = tasks.change_status(session, task.id, TaskStatus.PLANNED, horizon_start=MON)

    assert isinstance(result, PlanningProposal)
    assert task.status == TaskStatus.INBOX
    assert task.queue_position is None
    assert session.query(PlanningSegment).count() == 0


def test_ready_applies_immediately_and_keeps_the_segments(session):
    task = plan(session)
    before = [(s.day, s.minutes) for s in session.query(PlanningSegment)]

    result = tasks.change_status(session, task.id, TaskStatus.READY)

    # §11.5: READY non libera capacità, il piano resta identico.
    assert isinstance(result, Task)
    assert result.status == TaskStatus.READY
    assert [(s.day, s.minutes) for s in session.query(PlanningSegment)] == before
    assert session.query(PlanningProposal).filter_by(status="pending").count() == 0
    assert session.query(Action).filter_by(action_type="STATUS_READY").count() == 1


def test_forbidden_transition_is_rejected(session):
    task = tasks.quick_add(session, "A")
    with pytest.raises(tasks.InvalidTransitionError):
        tasks.change_status(session, task.id, TaskStatus.DELIVERED, horizon_start=MON)


def test_effort_of_a_queued_task_cannot_be_edited_directly(session):
    task = plan(session)
    with pytest.raises(ValueError):
        tasks.update_task(session, task.id, planning_effort_minutes=60)


def test_position_between_is_fractional(session):
    assert tasks.position_between(None, None) == Decimal(1000)
    assert tasks.position_between(Decimal(1000), None) == Decimal(2000)
    assert tasks.position_between(Decimal(1000), Decimal(2000)) == Decimal(1500)
    assert tasks.position_between(None, Decimal(1000)) == Decimal(500)


def test_position_between_reports_exhausted_precision():
    before = Decimal("1000.0000000")
    after = before + Decimal("0.00000001")
    assert tasks.position_between(before, after) is None


def test_queue_is_renumbered_when_precision_runs_out(session):
    first, second = plan(session, "A"), plan(session, "B")
    first.queue_position = Decimal("1000")
    second.queue_position = Decimal("1000.00000001")
    session.flush()

    third = plan(session, "C")
    position = tasks.position_for(session, first.id, second.id)

    assert [t.queue_position for t in tasks.queued_tasks(session)] == [
        Decimal(1000), Decimal(2000), Decimal(3000)
    ]
    assert Decimal(1000) < position < Decimal(2000)
    assert third.queue_position == Decimal(3000)


def test_move_in_queue_only_proposes(session):
    first, second = plan(session, "A"), plan(session, "B")
    proposal = tasks.move_in_queue(session, second.id, MON, after_id=first.id)

    assert isinstance(proposal, PlanningProposal)
    assert second.queue_position > first.queue_position  # non ancora spostato
