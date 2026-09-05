"""Capacità settimanale ed eccezioni (§11.2, §11.3)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    CapacityException,
    ExceptionKind,
    PlanningProposal,
    PlanningSegment,
    ProposalKind,
    ProposalOrigin,
    WeeklyCapacity,
)
from . import proposals
from .planning import DEFAULT_WEEKLY, weekly_minutes


def weekly_capacity(session: Session) -> dict[int, int]:
    return weekly_minutes(session)


def set_weekly_capacity(session: Session, minutes_by_weekday: dict[int, int]) -> None:
    """Capacità standard. È una configurazione, non un evento sul piano: il
    ricalcolo passa comunque da una proposal alla prima simulazione (§11.2)."""
    if not session.scalars(select(WeeklyCapacity.weekday)).first():
        # Un aggiornamento parziale non deve azzerare i giorni non citati.
        session.add_all(
            WeeklyCapacity(weekday=w, minutes=m) for w, m in DEFAULT_WEEKLY.items()
        )
        session.flush()
    for weekday, minutes in minutes_by_weekday.items():
        row = session.get(WeeklyCapacity, weekday)
        if row is None:
            session.add(WeeklyCapacity(weekday=weekday, minutes=minutes))
        else:
            row.minutes = minutes
    session.commit()


def list_exceptions(session: Session, start: date, end: date) -> list[CapacityException]:
    return list(
        session.scalars(
            select(CapacityException).where(
                CapacityException.deleted_at.is_(None),
                CapacityException.day >= start,
                CapacityException.day <= end,
            ).order_by(CapacityException.day)
        )
    )


def _impacts_plan(session: Session, day: date) -> bool:
    """Un'eccezione tocca il piano solo se c'è lavoro pianificato da quel giorno in poi."""
    return session.scalars(
        select(PlanningSegment.id).where(PlanningSegment.day >= day).limit(1)
    ).first() is not None


def set_exception(
    session: Session,
    day: date,
    minutes: int,
    horizon_start: date,
    kind: ExceptionKind = ExceptionKind.LEAVE,
    note: str | None = None,
    origin: ProposalOrigin = ProposalOrigin.UI,
    originator: str | None = None,
) -> CapacityException | PlanningProposal:
    """§11.3: se c'è un piano da spostare la modifica passa da una proposal."""
    if _impacts_plan(session, day):
        return proposals.propose(
            session, ProposalKind.CAPACITY_CHANGE, origin,
            {"capacity": {day.isoformat(): int(minutes)}}, horizon_start, originator,
        )
    row = session.scalars(
        select(CapacityException).where(CapacityException.day == day)
    ).first()
    if row is None:
        row = CapacityException(day=day, minutes=int(minutes), kind=kind, note=note)
        session.add(row)
    else:
        row.minutes, row.kind, row.note, row.deleted_at = int(minutes), kind, note, None
    session.commit()
    return row


def remove_exception(
    session: Session,
    day: date,
    horizon_start: date,
    origin: ProposalOrigin = ProposalOrigin.UI,
    originator: str | None = None,
) -> CapacityException | PlanningProposal | None:
    if _impacts_plan(session, day):
        return proposals.propose(
            session, ProposalKind.CAPACITY_CHANGE, origin,
            {"capacity": {day.isoformat(): None}}, horizon_start, originator,
        )
    row = session.scalars(
        select(CapacityException).where(
            CapacityException.day == day, CapacityException.deleted_at.is_(None)
        )
    ).first()
    if row is not None:
        row.deleted_at = datetime.now(UTC)  # §23.2
        session.commit()
    return row
