"""Snapshot, action log, undo e redo (§22, §23, §25).

Snapshot e action stanno nello stesso modulo perché sono la stessa storia vista
da due lati: l'action dice cosa è stato deciso, lo snapshot com'era il piano dopo.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..models import Action, PlanningSnapshot
from ..schemas import (
    ActionView,
    ProposalView,
    SnapshotDetailView,
    SnapshotView,
    UndoView,
)
from ..services import history as service
from .deps import Caller, DbSession, Today

router = APIRouter(prefix="/api", tags=["history"])


@router.get("/snapshots", response_model=list[SnapshotView])
def list_snapshots(session: DbSession, principal: Caller, limit: int = 50):
    return list(
        session.scalars(
            select(PlanningSnapshot)
            .order_by(PlanningSnapshot.plan_version.desc()).limit(limit)
        )
    )


@router.get("/snapshots/{snapshot_id}", response_model=SnapshotDetailView)
def get_snapshot(snapshot_id: uuid.UUID, session: DbSession, principal: Caller):
    snapshot = session.get(PlanningSnapshot, snapshot_id)
    if snapshot is None:
        raise HTTPException(404, "snapshot not found")
    return snapshot


@router.get("/actions", response_model=list[ActionView])
def list_actions(session: DbSession, principal: Caller, limit: int = 50):
    return service.history(session, limit)


@router.get("/actions/{action_id}", response_model=ActionView)
def get_action(action_id: uuid.UUID, session: DbSession, principal: Caller):
    action = session.get(Action, action_id)
    if action is None:
        raise HTTPException(404, "action not found")
    return action


def _outcome(result: service.UndoOutcome) -> UndoView:
    return UndoView(
        status=result.status,
        message=result.message,
        action=ActionView.model_validate(result.action) if result.action else None,
        proposal=ProposalView.model_validate(result.proposal) if result.proposal else None,
    )


@router.post("/actions/{action_id}/undo", response_model=UndoView)
def undo(action_id: uuid.UUID, session: DbSession, principal: Caller, day: Today) -> UndoView:
    """§23.3-23.4: se l'undo tocca il piano non si applica, si propone."""
    return _outcome(service.undo(session, action_id, day))


@router.post("/actions/{action_id}/redo", response_model=UndoView)
def redo(action_id: uuid.UUID, session: DbSession, principal: Caller, day: Today) -> UndoView:
    return _outcome(service.redo(session, action_id, day))
