"""Planning Proposal: lista, dettaglio, approve/reject/recalculate (§12, §25, §26)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..models import PlanningProposal, ProposalStatus
from ..schemas import ProposalView, SnapshotView
from ..services import proposals as service
from .deps import Caller, DbSession, Today

router = APIRouter(prefix="/api/proposals", tags=["proposals"])


@router.get("", response_model=list[ProposalView])
def list_proposals(session: DbSession, principal: Caller, status: ProposalStatus | None = None):
    stmt = select(PlanningProposal).order_by(PlanningProposal.created_at.desc())
    if status is not None:
        stmt = stmt.where(PlanningProposal.status == status)
    return list(session.scalars(stmt))


def _get(session, proposal_id: uuid.UUID) -> PlanningProposal:
    proposal = session.get(PlanningProposal, proposal_id)
    if proposal is None:
        raise HTTPException(404, "proposal not found")
    return proposal


@router.get("/{proposal_id}", response_model=ProposalView)
def get_proposal(proposal_id: uuid.UUID, session: DbSession, principal: Caller):
    return _get(session, proposal_id)


@router.post("/{proposal_id}/approve", response_model=SnapshotView)
def approve(proposal_id: uuid.UUID, session: DbSession, principal: Caller):
    """§26: transazionale. Stale -> 409, conflitto hard -> 422 (vedi main.py)."""
    _get(session, proposal_id)
    return service.approve(session, proposal_id)


@router.post("/{proposal_id}/reject", response_model=ProposalView)
def reject(proposal_id: uuid.UUID, session: DbSession, principal: Caller):
    _get(session, proposal_id)
    return service.reject(session, proposal_id)


@router.post("/{proposal_id}/recalculate", response_model=ProposalView)
def recalculate(proposal_id: uuid.UUID, session: DbSession, principal: Caller, day: Today):
    """§12.1: una proposal stale va ricalcolata prima di poter essere approvata."""
    _get(session, proposal_id)
    proposal = service.recalculate(session, proposal_id, day)
    session.commit()
    return proposal
