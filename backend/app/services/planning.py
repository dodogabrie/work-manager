"""Ponte fra il DB e lo scheduler puro (§29).

Nessuna funzione qui muta il piano: legge le entità, le traduce nei dataclass
del dominio, esegue la simulazione e riserializza. Le mutazioni stanno in
`proposals.approve`.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..domain.capacity import CalendarEvent, CapacityCalendar, busy_minutes_by_day
from ..domain.diff import PlanChange
from ..domain.models import PlanningReason, QueueItem, ScheduleResult
from ..domain.models import PlanningSegment as DomainSegment
from ..domain.scheduler import MAX_HORIZON_DAYS, schedule
from ..models import (
    CalendarEventStatus,
    CapacityException,
    ExternalCalendarEvent,
    PlanningSegment,
    PlanState,
    Task,
    TaskStatus,
    WeeklyCapacity,
)

TZ = ZoneInfo(settings.tz)

#: §11.2: la capacità di default se la tabella non è ancora stata configurata.
DEFAULT_WEEKLY = {0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0}

#: I task che occupano capacità pianificata (§7). READY/DELIVERED restano
#: allocati ma non hanno più effort da piazzare (§11.5), quindi non entrano
#: in coda: i loro segmenti sono già congelati.
QUEUE_STATUSES = (TaskStatus.PLANNED, TaskStatus.IN_PROGRESS)


# ---------------------------------------------------------------- plan state

def plan_state(session: Session, *, for_update: bool = False) -> PlanState:
    """La riga singleton, creata al primo accesso."""
    stmt = select(PlanState).where(PlanState.id == 1)
    if for_update:
        stmt = stmt.with_for_update()  # §26: lock di riga, ignorato da SQLite nei test
    state = session.execute(stmt).scalar_one_or_none()
    if state is None:
        state = PlanState(id=1, version=0)
        session.add(state)
        session.flush()
    return state


def plan_version(session: Session) -> int:
    return plan_state(session).version


def bump_plan_version(session: Session) -> int:
    state = plan_state(session, for_update=True)
    state.version += 1
    state.updated_at = datetime.now(UTC)
    session.flush()
    return state.version


# ---------------------------------------------------------------- lettura

def frozen_segments(
    session: Session, horizon_start: date | None = None
) -> list[DomainSegment]:
    """Segmenti che la ri-simulazione non può muovere (§32.2.8).

    Sono quelli marcati `locked` e — se si pianifica da `horizon_start` — quelli
    già nel passato: lo scheduler non li rigenererebbe e andrebbero persi.
    """
    rows = session.scalars(select(PlanningSegment)).all()
    return [
        DomainSegment(str(s.task_id), s.day, s.minutes, locked=True)
        for s in rows
        if s.locked or (horizon_start is not None and s.day < horizon_start)
    ]


def _frozen_minutes(session: Session, horizon_start: date | None) -> dict[str, int]:
    minutes: dict[str, int] = {}
    for seg in frozen_segments(session, horizon_start):
        minutes[seg.task_id] = minutes.get(seg.task_id, 0) + seg.minutes
    return minutes


def build_queue(
    session: Session,
    overrides: dict[str, dict[str, Any]] | None = None,
    horizon_start: date | None = None,
) -> list[QueueItem]:
    """La coda come la vede lo scheduler.

    `overrides` applica in memoria i campi di un intent senza toccare il DB:
    è così che si simula una proposal prima di approvarla (§3.3).
    L'effort esposto è quello ancora da piazzare: i minuti già congelati in
    segmenti locked sono stati scritti e non vanno ripianificati.
    """
    overrides = overrides or {}
    frozen = _frozen_minutes(session, horizon_start)
    items: list[QueueItem] = []
    for task in session.scalars(select(Task).where(Task.deleted_at.is_(None))):
        over = overrides.get(str(task.id), {})
        status = TaskStatus(over.get("status", task.status))
        position = over.get("queue_position", task.queue_position)
        if status not in QUEUE_STATUSES or position is None:
            continue
        effort = int(over.get("planning_effort_minutes", task.planning_effort_minutes))
        items.append(
            QueueItem(
                task_id=str(task.id),
                title=task.title,
                effort_minutes=max(0, effort - frozen.get(str(task.id), 0)),
                queue_position=Decimal(str(position)),
                created_at=task.created_at,
                target_date=task.target_delivery_date,
                fixed_date=task.fixed_delivery_date,
                project_id=str(task.project_id) if task.project_id else None,
            )
        )
    items.sort(key=lambda i: (i.queue_position, i.created_at, i.task_id))
    return items


def weekly_minutes(session: Session) -> dict[int, int]:
    rows = session.execute(select(WeeklyCapacity.weekday, WeeklyCapacity.minutes)).all()
    return {w: m for w, m in rows} or dict(DEFAULT_WEEKLY)


def build_capacity(
    session: Session,
    start: date,
    end: date,
    exception_overrides: dict[str, int | None] | None = None,
) -> CapacityCalendar:
    """Capacità schedulabile: base settimanale, eccezioni, meno le riunioni (§11.2-11.4)."""
    exceptions = {
        e.day: e.minutes
        for e in session.scalars(
            select(CapacityException).where(
                CapacityException.deleted_at.is_(None),
                CapacityException.day >= start,
                CapacityException.day <= end,
            )
        )
    }
    for raw_day, minutes in (exception_overrides or {}).items():
        day = date.fromisoformat(raw_day)
        if minutes is None:
            exceptions.pop(day, None)
        else:
            exceptions[day] = int(minutes)

    window_start = datetime.combine(start, datetime.min.time())
    window_end = datetime.combine(end + timedelta(days=1), datetime.min.time())
    events = [
        CalendarEvent(e.starts_at, e.ends_at, str(e.status))
        for e in session.scalars(
            select(ExternalCalendarEvent).where(
                ExternalCalendarEvent.cancelled.is_(False),
                ExternalCalendarEvent.status != CalendarEventStatus.DECLINED,
            )
        )
        if _overlaps(e, window_start, window_end)
    ]
    return CapacityCalendar(weekly_minutes(session), exceptions, busy_minutes_by_day(events, TZ))


def _overlaps(event: ExternalCalendarEvent, start: datetime, end: datetime) -> bool:
    starts, ends = _naive(event.starts_at), _naive(event.ends_at)
    return ends >= start and starts <= end


def _naive(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo else value


def current_plan(session: Session) -> ScheduleResult:
    """Il piano persistito, riletto senza rischedulare nulla."""
    segments = [
        DomainSegment(str(s.task_id), s.day, s.minutes, s.locked)
        for s in session.scalars(select(PlanningSegment).order_by(PlanningSegment.day))
    ]
    delivery: dict[str, date] = {}
    for seg in segments:
        if seg.date > delivery.get(seg.task_id, date.min):
            delivery[seg.task_id] = seg.date
    return ScheduleResult(tuple(segments), delivery)


def simulate(
    session: Session,
    horizon_start: date,
    queue_override: list[QueueItem] | None = None,
    locked: list[DomainSegment] | None = None,
    capacity: CapacityCalendar | None = None,
) -> ScheduleResult:
    if queue_override is None:
        queue_override = build_queue(session, horizon_start=horizon_start)
    frozen = frozen_segments(session, horizon_start) if locked is None else locked
    if capacity is None:
        capacity = build_capacity(
            session, horizon_start, horizon_start + timedelta(days=MAX_HORIZON_DAYS)
        )
    return schedule(queue_override, capacity, horizon_start, frozen)


# ---------------------------------------------------------------- scrittura segmenti

def rewrite_segments(session: Session, segments: list[dict[str, Any]]) -> None:
    """Riscrive i PlanningSegment dal risultato simulato: sono derivati (§24)."""
    for old in session.scalars(select(PlanningSegment)):
        session.delete(old)
    session.flush()
    for seg in segments:
        session.add(
            PlanningSegment(
                task_id=uuid.UUID(seg["task_id"]),
                day=date.fromisoformat(seg["date"]),
                minutes=int(seg["minutes"]),
                locked=bool(seg.get("locked", False)),
            )
        )
    session.flush()


# ---------------------------------------------------------------- serializzazione

def segment_json(seg: DomainSegment) -> dict[str, Any]:
    return {
        "task_id": seg.task_id,
        "date": seg.date.isoformat(),
        "minutes": seg.minutes,
        "locked": seg.locked,
    }


def reason_json(reason: PlanningReason) -> dict[str, Any]:
    data = asdict(reason)
    data["type"] = str(reason.type)
    data["date"] = reason.date.isoformat() if reason.date else None
    return data


def change_json(change: PlanChange) -> dict[str, Any]:
    return {
        "task_id": change.task_id,
        "old_start": change.old_start.isoformat() if change.old_start else None,
        "new_start": change.new_start.isoformat() if change.new_start else None,
        "old_delivery": change.old_delivery.isoformat() if change.old_delivery else None,
        "new_delivery": change.new_delivery.isoformat() if change.new_delivery else None,
        "shift_days": change.shift_days,
    }


def simulation_json(result: ScheduleResult, changes: list[PlanChange]) -> dict[str, Any]:
    """La forma che §44 richiede a una proposal."""
    return {
        "segments": [segment_json(s) for s in result.segments],
        "delivery_dates": {t: d.isoformat() for t, d in result.delivery_dates.items()},
        "changes": [change_json(c) for c in changes],
        "warnings": [reason_json(r) for r in result.warnings],
        "conflicts": [reason_json(r) for r in result.conflicts],
        "reasons": [reason_json(r) for r in result.reasons],
    }
