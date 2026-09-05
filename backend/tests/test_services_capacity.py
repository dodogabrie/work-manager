from __future__ import annotations

from datetime import date

from app.models import (
    CapacityException,
    ExceptionKind,
    PlanningProposal,
    PlanningSegment,
    TaskStatus,
)
from app.services import capacity, proposals, tasks

from .conftest import MON

TUE = date(2026, 1, 6)


def test_exception_without_a_plan_is_applied_directly(session):
    result = capacity.set_exception(session, TUE, 0, MON, kind=ExceptionKind.VACATION)

    assert isinstance(result, CapacityException)
    assert capacity.list_exceptions(session, MON, TUE) == [result]


def test_exception_on_an_existing_plan_goes_through_a_proposal(session):
    task = tasks.quick_add(session, "A", planning_effort_minutes=960)
    proposals.approve(
        session, tasks.change_status(session, task.id, TaskStatus.PLANNED, horizon_start=MON).id
    )

    result = capacity.set_exception(session, TUE, 0, MON, kind=ExceptionKind.VACATION)

    # §11.3: ferie su un piano esistente -> proposal -> before/after -> approvazione.
    assert isinstance(result, PlanningProposal)
    assert capacity.list_exceptions(session, MON, TUE) == []

    proposals.approve(session, result.id)
    days = sorted(s.day for s in session.query(PlanningSegment))
    assert TUE not in days and days == [MON, date(2026, 1, 7)]
    assert capacity.list_exceptions(session, MON, TUE)[0].minutes == 0


def test_weekly_capacity_round_trip(session):
    assert capacity.weekly_capacity(session)[0] == 480
    capacity.set_weekly_capacity(session, {0: 240, 5: 120})
    assert capacity.weekly_capacity(session) == {
        0: 240, 1: 480, 2: 480, 3: 480, 4: 480, 5: 120, 6: 0,
    }
