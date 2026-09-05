"""Task, inbox, effort, coda, stato (§6, §7, §8, §15, §25).

Router sottile: parse -> service -> DTO. Le operazioni che toccano il piano
restituiscono una proposal, non la applicano (§3.3).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..models import PlanningProposal, ProposalOrigin, Task, TaskStatus
from ..schemas import (
    CompleteIn,
    EffortChangeIn,
    EffortProposalIn,
    MoveIn,
    ProposalView,
    QuickAddIn,
    StatusChangeIn,
    TaskOrProposal,
    TaskPatchIn,
)
from ..services import tasks as service
from .deps import Caller, DbSession, Principal, Today, task_view

router = APIRouter(prefix="/api", tags=["tasks"])


def _origin(principal: Principal) -> ProposalOrigin:
    return ProposalOrigin.UI if principal.is_owner else ProposalOrigin.API


def _serialize(principal: Principal, task: Task):
    return task_view(principal).model_validate(task)


@router.get("/tasks")
def list_tasks(session: DbSession, principal: Caller, status: TaskStatus | None = None):
    stmt = select(Task).where(Task.deleted_at.is_(None))
    if status is not None:
        stmt = stmt.where(Task.status == status)
    stmt = stmt.order_by(Task.queue_position.is_(None), Task.queue_position, Task.created_at)
    view = task_view(principal)
    return [view.model_validate(t) for t in session.scalars(stmt)]


@router.get("/inbox")
def inbox(session: DbSession, principal: Caller):
    """§6.1: i task non ancora sottoposti allo scheduler."""
    return list_tasks(session, principal, status=TaskStatus.INBOX)


@router.post("/inbox/quick-add", status_code=201)
def quick_add(payload: QuickAddIn, session: DbSession, principal: Caller):
    """§6.2: basta il titolo."""
    task = service.quick_add(session, payload.title, **payload.model_dump(exclude={"title"}))
    return _serialize(principal, task)


@router.post("/tasks", status_code=201)
def create_task(payload: QuickAddIn, session: DbSession, principal: Caller):
    return quick_add(payload, session, principal)


@router.get("/tasks/{task_id}")
def get_task(task_id: uuid.UUID, session: DbSession, principal: Caller):
    task = session.get(Task, task_id)
    if task is None or task.deleted_at is not None:
        raise HTTPException(404, "task not found")
    return _serialize(principal, task)


@router.patch("/tasks/{task_id}")
def patch_task(task_id: uuid.UUID, payload: TaskPatchIn, session: DbSession, principal: Caller):
    fields = payload.model_dump(exclude_unset=True)
    return _serialize(principal, service.update_task(session, task_id, **fields))


@router.delete("/tasks/{task_id}")
def delete_task(task_id: uuid.UUID, session: DbSession, principal: Caller):
    return _serialize(principal, service.soft_delete(session, task_id))


@router.post("/tasks/{task_id}/effort/propose")
def propose_effort(
    task_id: uuid.UUID, payload: EffortProposalIn, session: DbSession, principal: Caller
):
    """§15.1: la stima proposta si deposita sul task e basta — non è ancora il
    planning effort, quindi non passa da una proposal."""
    task = service.update_task(
        session, task_id,
        proposed_effort_minutes=payload.minutes,
        proposed_effort_min_minutes=payload.min_minutes,
        proposed_effort_max_minutes=payload.max_minutes,
        estimate_confidence=payload.confidence,
        estimate_rationale=payload.rationale,
    )
    return _serialize(principal, task)


@router.post("/tasks/{task_id}/effort/change", response_model=ProposalView)
def change_effort(
    task_id: uuid.UUID, payload: EffortChangeIn, session: DbSession,
    principal: Caller, day: Today,
) -> PlanningProposal:
    """§15.3 / §37: la variazione di effort è esplicita e passa da proposal."""
    proposal = service.propose_effort_change(
        session, task_id, payload.minutes, day, _origin(principal), principal.name
    )
    session.commit()
    return proposal


@router.post("/tasks/{task_id}/status", response_model=TaskOrProposal)
def change_status(
    task_id: uuid.UUID, payload: StatusChangeIn, session: DbSession,
    principal: Caller, day: Today,
) -> TaskOrProposal:
    """READY/DELIVERED si applicano subito (§11.5); tutto il resto propone."""
    result = service.change_status(
        session, task_id, payload.status, day, _origin(principal), principal.name
    )
    if isinstance(result, PlanningProposal):
        session.commit()
        return TaskOrProposal(proposal=ProposalView.model_validate(result))
    return TaskOrProposal(task=_serialize(principal, result))


@router.post("/tasks/{task_id}/move", response_model=ProposalView)
def move(
    task_id: uuid.UUID, payload: MoveIn, session: DbSession,
    principal: Caller, day: Today,
) -> PlanningProposal:
    """§14 / R9: il riordino è un'intenzione, non una modifica del piano."""
    proposal = service.move_in_queue(
        session, task_id, day, payload.before_id, payload.after_id,
        _origin(principal), principal.name,
    )
    session.commit()
    return proposal


@router.post("/tasks/{task_id}/complete", response_model=ProposalView)
def complete(
    task_id: uuid.UUID, payload: CompleteIn, session: DbSession,
    principal: Caller, day: Today,
) -> PlanningProposal:
    """§46.2: COMPLETED è un evento esplicito e compatta in avanti."""
    proposal = service.propose_completion(
        session, task_id, day, payload.actual_minutes, _origin(principal), principal.name
    )
    session.commit()
    return proposal
