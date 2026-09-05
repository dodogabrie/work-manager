"""Planning Proposal: l'unica strada per cambiare il piano confermato (§3.3, §12, §26).

Un intent è normalizzato in due sole sezioni, qualunque sia il `kind`:

    {"tasks": {task_id: {campo: valore, ...}},   # status, queue_position, effort...
     "capacity": {"YYYY-MM-DD": minuti | null},  # null = elimina l'eccezione
     "completed": {task_id: minuti_effettivi | null}}

`kind` resta l'etichetta semantica per UI e report, ma non cambia il modo in cui
l'intent viene simulato e applicato: una sola implementazione delle regole (§29).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.diff import diff_plans
from ..domain.models import PlanningSegment as DomainSegment
from ..domain.scheduler import MAX_HORIZON_DAYS
from ..models import (
    Action,
    CapacityException,
    ExceptionKind,
    PlanningProposal,
    PlanningSegment,
    PlanningSnapshot,
    ProposalKind,
    ProposalOrigin,
    ProposalStatus,
    Task,
    TaskStatus,
)
from . import planning

TASK_FIELDS = (
    "status", "queue_position", "planning_effort_minutes",
    "target_delivery_date", "fixed_delivery_date",
    "ready_at", "delivered_at", "completed_at",
)
DATE_FIELDS = ("target_delivery_date", "fixed_delivery_date")
DATETIME_FIELDS = ("ready_at", "delivered_at", "completed_at")


class ProposalError(Exception):
    """Base delle condizioni che impediscono di applicare una proposal."""


class StaleProposalError(ProposalError):
    """§12.1: calcolata su una versione del piano non più corrente."""


class HardConflictError(ProposalError):
    """§14.1: un conflitto hard non è confermabile. I warning invece sì (§14.2)."""


class ProposalNotPendingError(ProposalError):
    pass


# ---------------------------------------------------------------- simulazione

def _projected_locked(
    session: Session, intent: dict[str, Any], horizon_start: date
) -> list[DomainSegment]:
    """Segmenti congelati come sarebbero dopo l'intent.

    §46.2: completare un task non cancella il lavoro già svolto — lo congela ai
    minuti effettivi e restituisce al bicchiere tutto il resto.
    """
    completed = intent.get("completed") or {}
    frozen = [s for s in planning.frozen_segments(session, horizon_start)
              if s.task_id not in completed]
    for task_id, actual in completed.items():
        frozen.extend(_completed_segments(session, task_id, actual, horizon_start))
    return frozen


def _completed_segments(
    session: Session, task_id: str, actual: int | None, horizon_start: date
) -> list[DomainSegment]:
    rows = session.scalars(
        select(PlanningSegment)
        .where(PlanningSegment.task_id == uuid.UUID(task_id))
        .order_by(PlanningSegment.day)
    ).all()
    if actual is None:
        actual = sum(s.minutes for s in rows if s.day < horizon_start)
    out: list[DomainSegment] = []
    left = int(actual)
    for row in rows:
        if left <= 0:
            break
        taken = min(left, row.minutes)
        out.append(DomainSegment(task_id, row.day, taken, locked=True))
        left -= taken
    if left > 0 and out:  # più lavoro dei segmenti esistenti: allunga l'ultimo
        last = out[-1]
        out[-1] = DomainSegment(last.task_id, last.date, last.minutes + left, locked=True)
    return out


def simulate_intent(session: Session, intent: dict[str, Any], horizon_start: date):
    capacity = planning.build_capacity(
        session,
        horizon_start,
        horizon_start + timedelta(days=MAX_HORIZON_DAYS),
        exception_overrides=intent.get("capacity"),
    )
    queue = planning.build_queue(
        session, overrides=intent.get("tasks"), horizon_start=horizon_start
    )
    # Un task completato esce dalla coda: il suo effort residuo sparisce (§46.2).
    completed = intent.get("completed") or {}
    queue = [i for i in queue if i.task_id not in completed]
    return planning.simulate(
        session, horizon_start,
        queue_override=queue,
        locked=_projected_locked(session, intent, horizon_start),
        capacity=capacity,
    )


def propose(
    session: Session,
    kind: ProposalKind,
    origin: ProposalOrigin,
    intent: dict[str, Any],
    horizon_start: date,
    originator: str | None = None,
) -> PlanningProposal:
    """Simula l'intent e lo salva come proposta. Non tocca il piano."""
    after = simulate_intent(session, intent, horizon_start)
    changes = diff_plans(planning.current_plan(session), after)
    proposal = PlanningProposal(
        kind=kind,
        origin=origin,
        originator=originator,
        status=ProposalStatus.PENDING,
        base_plan_version=planning.plan_version(session),
        intent=dict(intent, horizon_start=horizon_start.isoformat()),
        simulation=planning.simulation_json(after, changes),
    )
    session.add(proposal)
    session.flush()
    return proposal


def recalculate(
    session: Session, proposal_id: uuid.UUID, horizon_start: date
) -> PlanningProposal:
    """Ricalcola dalla versione corrente e riporta la proposal a PENDING (§12.1)."""
    proposal = session.get(PlanningProposal, proposal_id)
    if proposal.status in (ProposalStatus.APPLIED, ProposalStatus.REJECTED):
        raise ProposalNotPendingError(f"proposal {proposal_id} is {proposal.status}")
    after = simulate_intent(session, proposal.intent, horizon_start)
    changes = diff_plans(planning.current_plan(session), after)
    proposal.simulation = planning.simulation_json(after, changes)
    proposal.intent = dict(proposal.intent, horizon_start=horizon_start.isoformat())
    proposal.base_plan_version = planning.plan_version(session)
    proposal.status = ProposalStatus.PENDING
    session.flush()
    return proposal


def reject(session: Session, proposal_id: uuid.UUID) -> PlanningProposal:
    proposal = session.get(PlanningProposal, proposal_id)
    proposal.status = ProposalStatus.REJECTED
    proposal.resolved_at = datetime.now(UTC)
    session.commit()
    return proposal


# ---------------------------------------------------------------- applicazione

def _capture(session: Session, intent: dict[str, Any]) -> dict[str, Any]:
    """Stato attuale dei campi che l'intent tocca: è la base dell'undo (§23.3)."""
    tasks: dict[str, Any] = {}
    for task_id, fields in (intent.get("tasks") or {}).items():
        task = session.get(Task, uuid.UUID(task_id))
        if task is None:
            continue
        tasks[task_id] = {f: _json_value(getattr(task, f)) for f in fields if f in TASK_FIELDS}
    for task_id in (intent.get("completed") or {}):
        task = session.get(Task, uuid.UUID(task_id))
        if task is not None:
            tasks.setdefault(task_id, {}).update(
                {f: _json_value(getattr(task, f))
                 for f in ("status", "queue_position", "planning_effort_minutes", "completed_at")}
            )
    capacity: dict[str, Any] = {}
    for raw_day in (intent.get("capacity") or {}):
        row = _exception_row(session, date.fromisoformat(raw_day))
        capacity[raw_day] = None if row is None or row.deleted_at else row.minutes
    return {"tasks": tasks, "capacity": capacity}


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value) if isinstance(value, TaskStatus) else value


def _exception_row(session: Session, day: date) -> CapacityException | None:
    return session.scalars(
        select(CapacityException).where(CapacityException.day == day)
    ).first()


def apply_intent(session: Session, intent: dict[str, Any]) -> None:
    """Muta le entità. Chiamata solo da `approve`, dentro la sua transazione."""
    for task_id, fields in (intent.get("tasks") or {}).items():
        task = session.get(Task, uuid.UUID(task_id))
        if task is None:
            continue
        for field, value in fields.items():
            if field not in TASK_FIELDS:
                continue
            if field == "queue_position":
                value = None if value is None else Decimal(str(value))
            elif field == "status" and value is not None:
                value = TaskStatus(value)
            elif field in DATE_FIELDS and isinstance(value, str):
                value = date.fromisoformat(value)
            elif field in DATETIME_FIELDS and isinstance(value, str):
                value = datetime.fromisoformat(value)
            setattr(task, field, value)

    for task_id, actual in (intent.get("completed") or {}).items():
        task = session.get(Task, uuid.UUID(task_id))
        if task is None:
            continue
        task.queue_position = None
        task.completed_at = datetime.now(UTC)
        if task.status not in (TaskStatus.READY, TaskStatus.DELIVERED):
            task.status = TaskStatus.READY
        if actual is not None:
            task.planning_effort_minutes = int(actual)

    for raw_day, minutes in (intent.get("capacity") or {}).items():
        day = date.fromisoformat(raw_day)
        row = _exception_row(session, day)
        if minutes is None:
            if row is not None:
                row.deleted_at = datetime.now(UTC)  # §23.2 soft delete
        elif row is None:
            session.add(CapacityException(day=day, minutes=int(minutes),
                                          kind=ExceptionKind.LEAVE))
        else:
            # Il vincolo di unicità è sul giorno: una eccezione soft-deleted si
            # rianima invece di essere reinserita.
            row.minutes = int(minutes)
            row.deleted_at = None
    session.flush()


def _snapshot_payload(session: Session, version: int) -> dict[str, Any]:
    """§22: copia completa dello stato rilevante della timeline, non un diff."""
    return {
        "plan_version": version,
        "created_at": datetime.now(UTC).isoformat(),
        "segments": [
            planning.segment_json(s) for s in planning.current_plan(session).segments
        ],
        "tasks": [
            {
                "id": str(t.id),
                "title": t.title,
                "project_id": str(t.project_id) if t.project_id else None,
                "status": str(t.status),
                "queue_position": None if t.queue_position is None else str(t.queue_position),
                "planning_effort_minutes": t.planning_effort_minutes,
                "target_delivery_date": _json_value(t.target_delivery_date),
                "fixed_delivery_date": _json_value(t.fixed_delivery_date),
            }
            for t in session.scalars(select(Task).where(Task.deleted_at.is_(None)))
        ],
        "capacity": {
            "weekly": {str(w): m for w, m in planning.weekly_minutes(session).items()},
            "exceptions": {
                e.day.isoformat(): e.minutes
                for e in session.scalars(
                    select(CapacityException).where(CapacityException.deleted_at.is_(None))
                )
            },
        },
    }


def approve(session: Session, proposal_id: uuid.UUID) -> PlanningSnapshot:
    """Applica la proposal in una sola transazione (§26).

    Ordine obbligato: lock della riga di stato, controllo di versione, controllo
    dei conflitti hard, mutazione, riscrittura dei segmenti, bump, snapshot, action.
    """
    state = planning.plan_state(session, for_update=True)
    proposal = session.get(PlanningProposal, proposal_id)
    if proposal is None:
        raise ProposalError(f"proposal {proposal_id} not found")
    if proposal.status != ProposalStatus.PENDING:
        raise ProposalNotPendingError(f"proposal {proposal_id} is {proposal.status}")

    if proposal.base_plan_version != state.version:
        proposal.status = ProposalStatus.STALE
        session.commit()
        raise StaleProposalError(
            f"proposal computed on plan v{proposal.base_plan_version}, "
            f"current is v{state.version}"
        )
    if proposal.simulation.get("conflicts"):
        raise HardConflictError(
            "; ".join(c["message"] for c in proposal.simulation["conflicts"])
        )

    intent = proposal.intent
    before = _capture(session, intent)
    apply_intent(session, intent)
    planning.rewrite_segments(session, proposal.simulation["segments"])

    state.version += 1
    now = datetime.now(UTC)
    state.updated_at = now
    snapshot = PlanningSnapshot(
        plan_version=state.version,
        created_at=now,
        payload=_snapshot_payload(session, state.version),
        note=str(proposal.kind),
    )
    session.add(snapshot)
    session.flush()

    action = Action(
        action_type=str(proposal.kind),
        origin=proposal.origin,
        actor=proposal.originator,
        created_at=now,
        entities={
            "tasks": sorted(set(intent.get("tasks") or {}) | set(intent.get("completed") or {})),
            "capacity": sorted(intent.get("capacity") or {}),
            "proposal_id": str(proposal.id),
        },
        before=before,
        after={k: v for k, v in intent.items() if k in ("tasks", "capacity", "completed")},
        snapshot_id=snapshot.id,
        reversible=True,
        inverse_of_id=_uuid_or_none(intent.get("inverse_of")),
    )
    session.add(action)

    # §23.3: l'undo non cancella nulla, marca l'azione originale come annullata.
    original_id = _uuid_or_none(intent.get("inverse_of")) or _uuid_or_none(intent.get("redo_of"))
    if original_id is not None:
        original = session.get(Action, original_id)
        if original is not None:
            original.undone = intent.get("inverse_of") is not None

    proposal.status = ProposalStatus.APPLIED
    proposal.resolved_at = now
    session.commit()
    return snapshot


def _uuid_or_none(value: Any) -> uuid.UUID | None:
    return uuid.UUID(value) if isinstance(value, str) else None
