from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from app.domain.capacity import CapacityCalendar
from app.domain.models import PlanningSegment, QueueItem, ScheduleResult

MON = date(2026, 1, 5)  # a Monday
TUE = date(2026, 1, 6)
WED = date(2026, 1, 7)
THU = date(2026, 1, 8)
FRI = date(2026, 1, 9)
SAT = date(2026, 1, 10)
SUN = date(2026, 1, 11)
NEXT_MON = date(2026, 1, 12)

H = 60
WORKWEEK = {0: 8 * H, 1: 8 * H, 2: 8 * H, 3: 8 * H, 4: 8 * H, 5: 0, 6: 0}


def calendar(exceptions=None, busy=None) -> CapacityCalendar:
    return CapacityCalendar(WORKWEEK, exceptions or {}, busy or {})


def item(
    task_id: str,
    minutes: int,
    position: str | int,
    *,
    title: str | None = None,
    target: date | None = None,
    fixed: date | None = None,
) -> QueueItem:
    return QueueItem(
        task_id=task_id,
        title=title or task_id,
        effort_minutes=minutes,
        queue_position=Decimal(str(position)),
        created_at=datetime(2026, 1, 1, 9, 0),
        target_date=target,
        fixed_date=fixed,
    )


def by_day(result: ScheduleResult) -> dict[date, list[tuple[str, int]]]:
    """Segments grouped per day, in plan order — the shape of the spec's tables."""
    days: dict[date, list[tuple[str, int]]] = {}
    for seg in result.segments:
        days.setdefault(seg.date, []).append((seg.task_id, seg.minutes))
    return days


def locked(task_id: str, day: date, minutes: int) -> PlanningSegment:
    return PlanningSegment(task_id, day, minutes, locked=True)
