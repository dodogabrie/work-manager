from __future__ import annotations

from app.models import Action, PlanningSegment, ProposalKind, ProposalOrigin, Task, TaskStatus
from app.services import history, proposals, tasks

from .conftest import MON


def plan(session, title, minutes=480):
    task = tasks.quick_add(session, title, planning_effort_minutes=minutes)
    proposals.approve(
        session, tasks.change_status(session, task.id, TaskStatus.PLANNED, horizon_start=MON).id
    )
    return task


def test_undo_of_a_plan_action_produces_a_proposal(session):
    task = plan(session, "A")
    action = session.query(Action).filter_by(action_type=str(ProposalKind.TASK_PLANNED)).one()

    outcome = history.undo(session, action.id, MON)

    # §23.3: contro-operazione sullo stato corrente -> proposal, non applicazione.
    assert outcome.status == "proposal"
    assert task.status == TaskStatus.PLANNED
    assert session.query(PlanningSegment).count() == 1
    assert outcome.proposal.kind == ProposalKind.UNDO
    assert outcome.proposal.intent["tasks"][str(task.id)]["status"] == "INBOX"


def test_undo_creates_an_inverse_action_without_deleting_the_original(session):
    task = plan(session, "A")
    original = session.query(Action).filter_by(action_type=str(ProposalKind.TASK_PLANNED)).one()
    original_id = original.id

    proposals.approve(session, history.undo(session, original_id, MON).proposal.id)

    assert session.get(Action, original_id) is not None  # §23.3: nulla viene cancellato
    assert original.undone is True
    inverse = session.query(Action).filter_by(inverse_of_id=original_id).one()
    assert inverse.id != original_id
    assert task.status == TaskStatus.INBOX
    assert task.queue_position is None
    assert session.query(PlanningSegment).count() == 0


def test_non_linear_undo_of_an_older_action(session):
    first, second, third = plan(session, "A"), plan(session, "B"), plan(session, "C")
    actions = session.query(Action).order_by(Action.created_at).all()
    oldest = actions[0]

    outcome = history.undo(session, oldest.id, MON)
    proposals.approve(session, outcome.proposal.id)

    # §23.4: si annulla qualsiasi azione reversibile, non solo l'ultima.
    assert first.status == TaskStatus.INBOX
    assert second.status == third.status == TaskStatus.PLANNED
    remaining = {s.task_id for s in session.query(PlanningSegment)}
    assert remaining == {second.id, third.id}


def test_undo_of_a_non_reversible_action_is_refused(session):
    action = history.record(
        session, "REPORT_GENERATED", ProposalOrigin.SYSTEM, entities={"report": "planning"}
    )
    session.commit()

    outcome = history.undo(session, action.id, MON)

    assert outcome.status == "impossible"
    assert "not reversible" in outcome.message
    assert action.undone is False


def test_undo_of_an_action_that_does_not_touch_the_plan_is_applied_directly(session):
    task = plan(session, "A")
    tasks.change_status(session, task.id, TaskStatus.READY)
    action = session.query(Action).filter_by(action_type="STATUS_READY").one()
    segments = session.query(PlanningSegment).count()

    outcome = history.undo(session, action.id, MON)

    assert outcome.status == "applied"
    assert session.get(Task, task.id).status == TaskStatus.PLANNED
    assert outcome.action.inverse_of_id == action.id
    assert action.undone is True
    assert session.query(PlanningSegment).count() == segments  # §11.5


def test_undo_twice_is_impossible(session):
    task = plan(session, "A")
    tasks.change_status(session, task.id, TaskStatus.READY)
    action = session.query(Action).filter_by(action_type="STATUS_READY").one()
    history.undo(session, action.id, MON)

    assert history.undo(session, action.id, MON).status == "impossible"


def test_redo_reapplies_the_action_semantically(session):
    task = plan(session, "A")
    tasks.change_status(session, task.id, TaskStatus.READY)
    action = session.query(Action).filter_by(action_type="STATUS_READY").one()
    history.undo(session, action.id, MON)

    outcome = history.redo(session, action.id, MON)

    assert outcome.status == "applied"
    assert session.get(Task, task.id).status == TaskStatus.READY
    assert action.undone is False
