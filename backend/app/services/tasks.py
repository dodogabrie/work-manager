"""Task, coda e transizioni di stato (§6, §7, §8, §11.5)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    ALLOWED_TRANSITIONS,
    TRANSITIONS_REQUIRING_PROPOSAL,
    PlanningProposal,
    ProposalKind,
    ProposalOrigin,
    Task,
    TaskStatus,
)
from . import history, proposals
from .planning import QUEUE_STATUSES

#: §8: le posizioni sono chiavi d'ordine opache, non indici. Il primo task parte
#: da 1000 e i nuovi vanno in fondo a +1000 (R3).
POSITION_STEP = Decimal(1000)

#: Numeric(20, 10): sotto questo scarto un punto medio non è più rappresentabile
#: e la coda va rinumerata.
MIN_GAP = Decimal("0.0000001")


class InvalidTransitionError(ValueError):
    """§7: transizione non prevista dalla macchina a stati."""


# ---------------------------------------------------------------- CRUD

def quick_add(session: Session, title: str, **fields: Any) -> Task:
    """§6.2: solo il titolo è obbligatorio. Il task nasce in INBOX, fuori dal piano."""
    if not title or not title.strip():
        raise ValueError("title is required")
    task = Task(title=title.strip(), status=TaskStatus.INBOX, **fields)
    session.add(task)
    session.commit()
    return task


def update_task(session: Session, task_id: uuid.UUID, **fields: Any) -> Task:
    """Campi che non toccano il piano. L'effort di un task in coda passa da
    `propose_effort_change`: cambiarlo qui sposterebbe il piano confermato (§15.3)."""
    task = _get(session, task_id)
    if "planning_effort_minutes" in fields and task.queue_position is not None:
        raise ValueError("effort of a queued task changes through a proposal (§15.3)")
    for field, value in fields.items():
        setattr(task, field, value)
    session.commit()
    return task


def soft_delete(session: Session, task_id: uuid.UUID) -> Task:
    """§23.2: soft delete, così la history resta leggibile."""
    task = _get(session, task_id)
    task.deleted_at = datetime.now(UTC)
    task.queue_position = None
    session.commit()
    return task


def _get(session: Session, task_id: uuid.UUID) -> Task:
    task = session.get(Task, task_id)
    if task is None or task.deleted_at is not None:
        raise LookupError(f"task {task_id} not found")
    return task


# ---------------------------------------------------------------- coda

def queued_tasks(session: Session) -> list[Task]:
    return list(
        session.scalars(
            select(Task)
            .where(
                Task.deleted_at.is_(None),
                Task.queue_position.is_not(None),
                Task.status.in_(QUEUE_STATUSES),
            )
            .order_by(Task.queue_position)
        )
    )


def position_between(before: Decimal | None, after: Decimal | None) -> Decimal | None:
    """Posizione fra due vicini. `None` significa "precisione esaurita, rinumera"."""
    if before is None and after is None:
        return POSITION_STEP
    if after is None:
        return before + POSITION_STEP
    if before is None:
        return after / 2 if after > MIN_GAP else None
    if after - before <= MIN_GAP:
        return None
    return (before + after) / 2


def renumber_queue(session: Session) -> None:
    """Riassegna 1000, 2000, ... mantenendo l'ordine: il piano non cambia,
    cambiano solo le chiavi d'ordine, quindi non serve una proposal (§8)."""
    for index, task in enumerate(queued_tasks(session), start=1):
        task.queue_position = POSITION_STEP * index
    session.flush()


def tail_position(session: Session) -> Decimal:
    """R3: un nuovo task va in fondo e non sposta il lavoro già approvato."""
    tasks = queued_tasks(session)
    return position_between(tasks[-1].queue_position if tasks else None, None)


def position_for(
    session: Session, before_id: uuid.UUID | None, after_id: uuid.UUID | None
) -> Decimal:
    """Posizione fra due task, rinumerando la coda se la precisione si esaurisce."""
    for attempt in range(2):
        before = session.get(Task, before_id).queue_position if before_id else None
        after = session.get(Task, after_id).queue_position if after_id else None
        position = position_between(before, after)
        if position is not None:
            return position
        if attempt == 0:
            renumber_queue(session)
    raise RuntimeError("queue renumbering did not free enough precision")


def move_in_queue(
    session: Session,
    task_id: uuid.UUID,
    horizon_start: date,
    before_id: uuid.UUID | None = None,
    after_id: uuid.UUID | None = None,
    origin: ProposalOrigin = ProposalOrigin.UI,
    originator: str | None = None,
) -> PlanningProposal:
    """§14 / R9: il drag & drop è un'intenzione, non una modifica."""
    position = position_for(session, before_id, after_id)
    return proposals.propose(
        session, ProposalKind.QUEUE_REORDER, origin,
        {"tasks": {str(task_id): {"queue_position": str(position)}}},
        horizon_start, originator,
    )


# ---------------------------------------------------------------- stato ed effort

def change_status(
    session: Session,
    task_id: uuid.UUID,
    target: TaskStatus,
    horizon_start: date | None = None,
    origin: ProposalOrigin = ProposalOrigin.UI,
    originator: str | None = None,
) -> Task | PlanningProposal:
    """Applica la transizione, oppure ne restituisce la proposal (§3.3, §11.5).

    READY e DELIVERED si applicano subito: marcare un task come pronto non
    libera capacità e non tocca i segmenti (§11.5).
    """
    task = _get(session, task_id)
    source = TaskStatus(task.status)
    if target not in ALLOWED_TRANSITIONS[source]:
        raise InvalidTransitionError(f"{source} -> {target} is not allowed")

    if (source, target) in TRANSITIONS_REQUIRING_PROPOSAL:
        if horizon_start is None:
            raise ValueError(f"{source} -> {target} needs a horizon_start: it changes the plan")
        fields: dict[str, Any] = {"status": str(target)}
        if target in QUEUE_STATUSES:
            fields["queue_position"] = (
                str(task.queue_position) if task.queue_position is not None
                else str(tail_position(session))
            )
        else:
            fields["queue_position"] = None
        return proposals.propose(
            session, _kind_for(target), origin, {"tasks": {str(task_id): fields}},
            horizon_start, originator,
        )

    task.status = target
    now = datetime.now(UTC)
    if target == TaskStatus.READY:
        task.ready_at = now
    elif target == TaskStatus.DELIVERED:
        task.delivered_at = now
    history.record(
        session, f"STATUS_{target}", origin, originator,
        entities={"tasks": [str(task_id)]},
        before={"tasks": {str(task_id): {"status": str(source)}}},
        after={"tasks": {str(task_id): {"status": str(target)}}},
    )
    session.commit()
    return task


def _kind_for(target: TaskStatus) -> ProposalKind:
    if target in QUEUE_STATUSES:
        return ProposalKind.TASK_PLANNED
    return ProposalKind.TASK_CANCELLED


def propose_effort_change(
    session: Session,
    task_id: uuid.UUID,
    minutes: int,
    horizon_start: date,
    origin: ProposalOrigin = ProposalOrigin.UI,
    originator: str | None = None,
) -> PlanningProposal:
    """§14.3: anche un resize grafico è una modifica dell'effort e passa di qui."""
    return proposals.propose(
        session, ProposalKind.EFFORT_CHANGE, origin,
        {"tasks": {str(task_id): {"planning_effort_minutes": int(minutes)}}},
        horizon_start, originator,
    )


def propose_completion(
    session: Session,
    task_id: uuid.UUID,
    horizon_start: date,
    actual_minutes: int | None = None,
    origin: ProposalOrigin = ProposalOrigin.UI,
    originator: str | None = None,
) -> PlanningProposal:
    """§46.2: il completamento esplicito elimina l'effort residuo e compatta in avanti."""
    return proposals.propose(
        session, ProposalKind.TASK_COMPLETED, origin,
        {"completed": {str(task_id): actual_minutes}},
        horizon_start, originator,
    )
