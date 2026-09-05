"""Forward-filling scheduler (§32.2, §43).

The queue order is the priority (R1). The scheduler walks time forward and pours
each task into the first available capacity (R2, "glass" model). It never
reorders, never scores, never looks at the clock.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date

from .capacity import CapacityCalendar
from .models import PlanningReason, PlanningSegment, QueueItem, ReasonType, ScheduleResult

MIN_SEGMENT_MINUTES = 30  # §32.2.8: smaller leftover holes are not filled
MAX_HORIZON_DAYS = 730
SCHEDULER_VERSION = "1"


def schedule(
    queue: Iterable[QueueItem],
    capacity: CapacityCalendar,
    horizon_start: date,
    locked_segments: Sequence[PlanningSegment] = (),
) -> ScheduleResult:
    """Materialise the queue into planning segments starting at `horizon_start`.

    `horizon_start` is injected: §32.2.8 plans from today as a whole day, never
    from "now".
    """
    # §32.2.8: locked segments consume capacity in their day and are never moved.
    segments: list[PlanningSegment] = [
        PlanningSegment(s.task_id, s.date, s.minutes, locked=True) for s in locked_segments
    ]
    used: dict[date, int] = {}
    for seg in segments:
        used[seg.date] = used.get(seg.date, 0) + seg.minutes

    # §32.2.8 tie-breaking: total order, therefore deterministic.
    ordered = sorted(queue, key=lambda i: (i.queue_position, i.created_at, i.task_id))

    days = capacity.iter_days(horizon_start)
    day = next(days)
    unplaced: dict[str, int] = {}

    for item in ordered:
        remaining = item.effort_minutes
        while remaining > 0:
            if (day - horizon_start).days > MAX_HORIZON_DAYS:
                unplaced[item.task_id] = remaining
                break
            free = capacity.available(day) - used.get(day, 0)
            # A hole shorter than the minimum segment is skipped, unless what is
            # left of the task fits in it entirely (§32.2.8).
            if free > 0 and (free >= MIN_SEGMENT_MINUTES or remaining <= free):
                taken = min(free, remaining)
                segments.append(PlanningSegment(item.task_id, day, taken))
                used[day] = used.get(day, 0) + taken
                remaining -= taken
                if remaining == 0:
                    break
            day = next(days)

    # Derived from the segments rather than tracked during placement: a task may
    # own a locked segment later than the work just poured in, and delivery is
    # the last day it occupies, not the last one written.
    delivery_dates: dict[str, date] = {}
    for seg in segments:
        known = delivery_dates.get(seg.task_id)
        if known is None or seg.date > known:
            delivery_dates[seg.task_id] = seg.date

    reasons: list[PlanningReason] = []
    for item in ordered:
        left = unplaced.get(item.task_id)
        if left:
            reasons.append(
                PlanningReason(
                    type=ReasonType.UNSCHEDULABLE,
                    severity="conflict",
                    message=(
                        f"{item.title} cannot be scheduled: {_fmt(left)} still unplanned "
                        f"after {MAX_HORIZON_DAYS} days of capacity."
                    ),
                    task_id=item.task_id,
                    minutes=left,
                )
            )
        delivery = delivery_dates.get(item.task_id)
        if delivery is None:
            continue
        if item.target_date is not None and delivery > item.target_date:
            reasons.append(
                PlanningReason(
                    type=ReasonType.TARGET_MISSED,
                    severity="warning",
                    message=(
                        f"Target missed because the current queue reaches {item.title} "
                        f"on {delivery}, after its target date {item.target_date}."
                    ),
                    task_id=item.task_id,
                    date=delivery,
                )
            )
        # §32.2.8: a fixed date is only a validator, never a reordering. One
        # conflict is emitted for each violated fixed date, not just the first.
        if item.fixed_date is not None and delivery > item.fixed_date:
            missing = sum(
                s.minutes
                for s in segments
                if s.task_id == item.task_id and s.date > item.fixed_date
            ) + unplaced.get(item.task_id, 0)
            reasons.append(
                PlanningReason(
                    type=ReasonType.FIXED_DATE_CONFLICT,
                    severity="conflict",
                    message=(
                        f"{item.title} is delivered on {delivery}, after its fixed date "
                        f"{item.fixed_date}. Missing capacity: {_fmt(missing)}."
                    ),
                    task_id=item.task_id,
                    date=item.fixed_date,
                    minutes=missing,
                )
            )

    # Stable sort: inside a day the segments keep locked-first, then queue order.
    segments.sort(key=lambda s: s.date)
    return ScheduleResult(
        segments=tuple(segments),
        delivery_dates=delivery_dates,
        reasons=tuple(reasons),
    )


def _fmt(minutes: int) -> str:
    hours, rest = divmod(minutes, 60)
    if hours and rest:
        return f"{hours}h {rest}m"
    return f"{hours}h" if hours else f"{rest}m"
