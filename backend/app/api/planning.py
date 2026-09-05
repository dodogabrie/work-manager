"""Piano corrente, contesto per Claude e simulazione (§13, §16.1, §25)."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter
from sqlalchemy import select

from ..domain.diff import diff_plans
from ..models import PlanningProposal, PlanningSegment, Project, ProposalStatus, Task, TaskStatus
from ..schemas import (
    DayCapacityView,
    PlanningContextView,
    PlanningSegmentView,
    PlanningView,
    ProjectView,
    ProposalView,
    SimulateIn,
    SimulationView,
    TaskClaudeView,
)
from ..services import planning as service
from ..services import proposals as proposal_service
from .deps import Caller, DbSession, Today, task_view

router = APIRouter(prefix="/api/planning", tags=["planning"])

#: Finestra di default della vista e del contesto: due settimane bastano a
#: rispondere "su cosa sono allocato" senza spedire mesi di segmenti a un LLM.
DEFAULT_DAYS = 14

#: §16.1: i vincoli che Claude deve conoscere per non proporre l'impossibile.
CONSTRAINTS = [
    "La posizione in coda è l'unica priorità: non esistono priority score (§8, R1).",
    "Lo scheduler riempie in avanti; un nuovo task va in fondo (R2, R3).",
    "Una fixed date è un vincolo hard che blocca l'approvazione; "
    "una target date è solo un warning (R8).",
    "Nessuna modifica al piano è diretta: ogni cambiamento passa da una proposal approvata (§3.3).",
    "Capacità recuperata non compatta il piano da sola (R6); solo COMPLETED compatta (R7).",
]


def _segments(session, start: date, end: date) -> list[PlanningSegment]:
    # L'ordine di lettura è definito una volta sola nel service (§33, R10).
    return list(session.scalars(service.segments_query(start, end)))


def _days(session, segments: list[PlanningSegment], start: date, end: date):
    capacity = service.build_capacity(session, start, end)
    planned: dict[date, int] = {}
    for seg in segments:
        planned[seg.day] = planned.get(seg.day, 0) + seg.minutes
    out = []
    day = start
    while day <= end:
        out.append(DayCapacityView(
            day=day,
            available_minutes=capacity.available(day),
            planned_minutes=planned.get(day, 0),
        ))
        day += timedelta(days=1)
    return out


@router.get("", response_model=PlanningView)
def get_planning(
    session: DbSession, principal: Caller, day: Today,
    start: date | None = None, end: date | None = None,
) -> PlanningView:
    start = start or day
    end = end or start + timedelta(days=DEFAULT_DAYS)
    segments = _segments(session, start, end)
    view = task_view(principal)
    tasks = session.scalars(
        select(Task).where(Task.deleted_at.is_(None), Task.queue_position.is_not(None))
        .order_by(Task.queue_position)
    )
    return PlanningView(
        plan_version=service.plan_version(session),
        tasks=[view.model_validate(t) for t in tasks],
        segments=[PlanningSegmentView.model_validate(s) for s in segments],
        days=_days(session, segments, start, end),
    )


@router.get("/context", response_model=PlanningContextView)
def context(session: DbSession, principal: Caller, day: Today) -> PlanningContextView:
    """§16.1: tutto ciò che serve a un LLM per ragionare, in una sola risposta."""
    end = day + timedelta(days=DEFAULT_DAYS)
    segments = _segments(session, day, end)
    inbox = session.scalars(
        select(Task).where(Task.deleted_at.is_(None), Task.status == TaskStatus.INBOX)
        .order_by(Task.created_at)
    )
    queue = session.scalars(
        select(Task).where(Task.deleted_at.is_(None), Task.queue_position.is_not(None))
        .order_by(Task.queue_position)
    )
    projects = session.scalars(
        select(Project).where(Project.deleted_at.is_(None), Project.archived.is_(False))
        .order_by(Project.name)
    )
    pending = session.scalars(
        select(PlanningProposal)
        .where(PlanningProposal.status == ProposalStatus.PENDING)
        .order_by(PlanningProposal.created_at)
    )
    return PlanningContextView(
        today=day,
        plan_version=service.plan_version(session),
        projects=[ProjectView.model_validate(p) for p in projects],
        inbox=[TaskClaudeView.model_validate(t) for t in inbox],
        queue=[TaskClaudeView.model_validate(t) for t in queue],
        segments=[PlanningSegmentView.model_validate(s) for s in segments],
        capacity=_days(session, segments, day, end),
        pending_proposals=[ProposalView.model_validate(p) for p in pending],
        constraints=CONSTRAINTS,
    )


@router.post("/simulate", response_model=SimulationView)
def simulate(payload: SimulateIn, session: DbSession, principal: Caller, day: Today):
    """§13: stessa semantica della preview della UI, senza creare nulla."""
    intent = payload.model_dump()
    after = proposal_service.simulate_intent(session, intent, day)
    changes = diff_plans(service.current_plan(session), after)
    return service.simulation_json(after, changes)
