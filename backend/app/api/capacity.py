"""Capacità settimanale ed eccezioni (§11.2, §11.3, §25)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException

from ..models import CapacityException, ExceptionKind, PlanningProposal
from ..schemas import (
    CapacityExceptionIn,
    CapacityExceptionPatchIn,
    CapacityExceptionView,
    CapacityView,
    ExceptionOrProposal,
    ProposalView,
)
from ..services import capacity as service
from .deps import Caller, DbSession, Today
from .planning import DEFAULT_DAYS, _days, _segments
from .tasks import _origin

router = APIRouter(prefix="/api/capacity", tags=["capacity"])


@router.get("", response_model=CapacityView)
def get_capacity(
    session: DbSession, principal: Caller, day: Today,
    start: date | None = None, end: date | None = None,
) -> CapacityView:
    start = start or day
    end = end or start + timedelta(days=DEFAULT_DAYS)
    return CapacityView(
        weekly_minutes=service.weekly_capacity(session),
        exceptions=[
            CapacityExceptionView.model_validate(e)
            for e in service.list_exceptions(session, start, end)
        ],
        days=_days(session, _segments(session, start, end), start, end),
    )


def _result(value: CapacityException | PlanningProposal | None) -> ExceptionOrProposal:
    """§11.3: se c'è un piano da spostare il service restituisce una proposal."""
    if isinstance(value, PlanningProposal):
        return ExceptionOrProposal(proposal=ProposalView.model_validate(value))
    if value is None:
        raise HTTPException(404, "capacity exception not found")
    return ExceptionOrProposal(exception=CapacityExceptionView.model_validate(value))


@router.post("/exceptions", response_model=ExceptionOrProposal, status_code=201)
def create_exception(
    payload: CapacityExceptionIn, session: DbSession, principal: Caller, day: Today
) -> ExceptionOrProposal:
    result = service.set_exception(
        session, payload.day, payload.minutes, day,
        ExceptionKind(payload.kind), payload.note, _origin(principal), principal.name,
    )
    session.commit()
    return _result(result)


def _exception(session, exception_id: uuid.UUID) -> CapacityException:
    row = session.get(CapacityException, exception_id)
    if row is None or row.deleted_at is not None:
        raise HTTPException(404, "capacity exception not found")
    return row


@router.patch("/exceptions/{exception_id}", response_model=ExceptionOrProposal)
def patch_exception(
    exception_id: uuid.UUID, payload: CapacityExceptionPatchIn,
    session: DbSession, principal: Caller, day: Today,
) -> ExceptionOrProposal:
    row = _exception(session, exception_id)
    result = service.set_exception(
        session, row.day, payload.minutes, day,
        ExceptionKind(payload.kind) if payload.kind else ExceptionKind(row.kind),
        payload.note if payload.note is not None else row.note,
        _origin(principal), principal.name,
    )
    session.commit()
    return _result(result)


@router.delete("/exceptions/{exception_id}", response_model=ExceptionOrProposal)
def delete_exception(
    exception_id: uuid.UUID, session: DbSession, principal: Caller, day: Today
) -> ExceptionOrProposal:
    row = _exception(session, exception_id)
    result = service.remove_exception(
        session, row.day, day, _origin(principal), principal.name
    )
    session.commit()
    return _result(result)
