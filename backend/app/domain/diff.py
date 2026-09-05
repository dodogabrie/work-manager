"""Before/after comparison of two plans — feeds the preview (§13) and the Impact Report (§21)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from .models import PlanningReason, PlanningSegment, ReasonType, ScheduleResult


@dataclass(frozen=True, slots=True)
class PlanChange:
    task_id: str
    old_start: date | None
    new_start: date | None
    old_delivery: date | None
    new_delivery: date | None
    shift_days: int


def diff_plans(before: ScheduleResult, after: ScheduleResult) -> list[PlanChange]:
    """One entry per task whose start or delivery date moved."""
    starts_before = _starts(before.segments)
    starts_after = _starts(after.segments)
    changes: list[PlanChange] = []
    for task_id in sorted(set(starts_before) | set(starts_after) | set(before.delivery_dates)
                          | set(after.delivery_dates)):
        old_start = starts_before.get(task_id)
        new_start = starts_after.get(task_id)
        old_delivery = before.delivery_dates.get(task_id)
        new_delivery = after.delivery_dates.get(task_id)
        if old_start == new_start and old_delivery == new_delivery:
            continue
        shift = (
            (new_delivery - old_delivery).days
            if old_delivery is not None and new_delivery is not None
            else 0
        )
        changes.append(
            PlanChange(task_id, old_start, new_start, old_delivery, new_delivery, shift)
        )
    return changes


def explain(
    changes: Iterable[PlanChange], cause: ReasonType, because: str
) -> list[PlanningReason]:
    """Turn plan changes into readable reasons (§44)."""
    reasons = []
    for change in changes:
        if change.shift_days > 0:
            message = f"{change.task_id} moved forward to {change.new_delivery} because {because}."
        elif change.shift_days < 0:
            message = f"{change.task_id} moved earlier to {change.new_delivery} because {because}."
        else:
            message = f"{change.task_id} changed because {because}."
        reasons.append(
            PlanningReason(
                type=cause,
                severity="info",
                message=message,
                task_id=change.task_id,
                date=change.new_delivery,
                minutes=None,
            )
        )
    return reasons


def _starts(segments: tuple[PlanningSegment, ...]) -> dict[str, date]:
    starts: dict[str, date] = {}
    for seg in segments:
        known = starts.get(seg.task_id)
        if known is None or seg.date < known:
            starts[seg.task_id] = seg.date
    return starts
