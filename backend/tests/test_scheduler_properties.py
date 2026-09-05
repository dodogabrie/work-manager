"""Property-based invariants of the scheduler (§32.2.7, §32.19)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from app.domain.capacity import CapacityCalendar
from app.domain.models import QueueItem, ReasonType
from app.domain.scheduler import schedule

START = date(2026, 1, 5)

weekly = st.dictionaries(
    st.integers(min_value=0, max_value=6),
    st.integers(min_value=0, max_value=600),
    min_size=1,
)
exceptions = st.dictionaries(
    st.builds(lambda n: START + timedelta(days=n), st.integers(min_value=0, max_value=20)),
    st.integers(min_value=0, max_value=600),
    max_size=5,
)
busy = st.dictionaries(
    st.builds(lambda n: START + timedelta(days=n), st.integers(min_value=0, max_value=20)),
    st.integers(min_value=0, max_value=600),
    max_size=5,
)
calendars = st.builds(CapacityCalendar, weekly, exceptions, busy)


@st.composite
def queues(draw: st.DrawFn) -> list[QueueItem]:
    efforts = draw(st.lists(st.integers(min_value=1, max_value=2000), min_size=1, max_size=8))
    return [
        QueueItem(
            task_id=f"T{i}",
            title=f"T{i}",
            effort_minutes=effort,
            queue_position=Decimal(i),
            created_at=datetime(2026, 1, 1, 9, 0),
        )
        for i, effort in enumerate(efforts)
    ]


@settings(max_examples=200, deadline=None)
@given(queues(), calendars)
def test_no_minute_is_lost_or_invented(queue: list[QueueItem], cal: CapacityCalendar) -> None:
    result = schedule(queue, cal, START)
    unschedulable = {c.task_id for c in result.conflicts if c.type is ReasonType.UNSCHEDULABLE}
    placed: dict[str, int] = {}
    for seg in result.segments:
        placed[seg.task_id] = placed.get(seg.task_id, 0) + seg.minutes
    for task in queue:
        if task.task_id in unschedulable:
            continue
        assert placed.get(task.task_id, 0) == task.effort_minutes


@settings(max_examples=200, deadline=None)
@given(queues(), calendars)
def test_no_day_exceeds_its_capacity(queue: list[QueueItem], cal: CapacityCalendar) -> None:
    result = schedule(queue, cal, START)
    used: dict[date, int] = {}
    for seg in result.segments:
        used[seg.date] = used.get(seg.date, 0) + seg.minutes
    for day, minutes in used.items():
        assert minutes <= cal.available(day)


@settings(max_examples=200, deadline=None)
@given(queues(), calendars)
def test_first_segments_follow_the_queue_order(
    queue: list[QueueItem], cal: CapacityCalendar
) -> None:
    """R1/R2: the scheduler never lets a later task start before an earlier one."""
    result = schedule(queue, cal, START)
    starts: dict[str, date] = {}
    for seg in result.segments:  # segments are sorted by day
        starts.setdefault(seg.task_id, seg.date)
    previous: date | None = None
    for task in queue:
        start = starts.get(task.task_id)
        if start is None:
            continue
        if previous is not None:
            assert start >= previous
        previous = start


@settings(max_examples=200, deadline=None)
@given(queues(), calendars)
def test_zero_capacity_days_never_receive_work(
    queue: list[QueueItem], cal: CapacityCalendar
) -> None:
    result = schedule(queue, cal, START)
    for seg in result.segments:
        assert cal.available(seg.date) > 0


@settings(max_examples=100, deadline=None)
@given(queues(), calendars)
def test_never_schedules_before_the_horizon(
    queue: list[QueueItem], cal: CapacityCalendar
) -> None:
    result = schedule(queue, cal, START)
    for seg in result.segments:
        assert seg.date >= START
