"""Golden tests for §33-§46: expected plans are written by hand from the spec."""

from __future__ import annotations

from datetime import date

from app.domain.diff import diff_plans, explain
from app.domain.models import ReasonType
from app.domain.scheduler import schedule
from tests.helpers import (
    FRI,
    MON,
    NEXT_MON,
    SAT,
    THU,
    TUE,
    WED,
    H,
    by_day,
    calendar,
    item,
    locked,
)

# §33 initial queue, effort in minutes.
BASE_QUEUE = [
    item("T1", 5 * H, 1, title="Fix MAG import"),
    item("T2", 12 * H, 2, title="RAW processing API"),
    item("T3", 8 * H, 3, title="QC integration"),
    item("T4", 6 * H, 4, title="Manager export"),
    item("T5", 3 * H, 5, title="Release cliente", fixed=THU),
]

ABC_QUEUE = [
    item("A", 8 * H, 1),
    item("B", 8 * H, 2),
    item("C", 8 * H, 3),
]


def test_33_base_scenario() -> None:
    """§33 base scenario.

    The spec's table shows Thursday as `T3 1h + T4 4h + T5 3h` and Friday as
    `T4 2h`, i.e. T5 partly overtaking T4 to land on its fixed Thursday. That
    contradicts the frozen decision §32.2.8 ("fixed date = only a validator,
    never a reordering") and R1/R2/R8. The pure forward fill is authoritative:
    T5 lands on Friday and a FIXED_DATE_CONFLICT is raised, which is exactly the
    "the user has to reorder the queue" outcome the spec asks for.
    """
    result = schedule(BASE_QUEUE, calendar(), MON)

    assert by_day(result) == {
        MON: [("T1", 5 * H), ("T2", 3 * H)],
        TUE: [("T2", 8 * H)],
        WED: [("T2", 1 * H), ("T3", 7 * H)],
        THU: [("T3", 1 * H), ("T4", 6 * H), ("T5", 1 * H)],
        FRI: [("T5", 2 * H)],
    }
    assert result.delivery_dates == {
        "T1": MON,
        "T2": WED,
        "T3": THU,
        "T4": THU,
        "T5": FRI,
    }
    assert [c.type for c in result.conflicts] == [ReasonType.FIXED_DATE_CONFLICT]
    assert result.conflicts[0].task_id == "T5"
    assert result.conflicts[0].minutes == 2 * H


def test_34_new_monday_meeting_shifts_forward() -> None:
    """§34: a 2h Monday meeting takes Monday from 8h to 6h; the queue order is kept."""
    before = schedule(BASE_QUEUE, calendar(), MON)
    after = schedule(BASE_QUEUE, calendar(busy={MON: 2 * H}), MON)

    days = by_day(after)
    assert days[MON] == [("T1", 5 * H), ("T2", 1 * H)]
    assert days[TUE] == [("T2", 8 * H)]
    assert days[WED] == [("T2", 3 * H), ("T3", 5 * H)]
    assert days[THU] == [("T3", 3 * H), ("T4", 5 * H)]
    assert days[FRI] == [("T4", 1 * H), ("T5", 3 * H)]

    changes = {c.task_id: c for c in diff_plans(before, after)}
    assert changes["T4"].old_delivery == THU
    assert changes["T4"].new_delivery == FRI
    assert changes["T4"].shift_days == 1

    reasons = explain(
        diff_plans(before, after),
        ReasonType.CAPACITY_REDUCED,
        "Monday capacity was reduced by 2h",
    )
    assert [r.type for r in reasons] == [ReasonType.CAPACITY_REDUCED] * len(reasons)
    assert any("T4 moved forward" in r.message for r in reasons)


def test_35_new_task_goes_last_and_moves_nothing() -> None:
    """§35: a new 6h task enters at the end of the queue and moves no planned work."""
    before = schedule(ABC_QUEUE, calendar(), MON)
    after = schedule([*ABC_QUEUE, item("X", 6 * H, 4)], calendar(), MON)

    assert by_day(before) == {MON: [("A", 8 * H)], TUE: [("B", 8 * H)], WED: [("C", 8 * H)]}
    assert [c.task_id for c in diff_plans(before, after)] == ["X"]
    assert after.delivery_dates["X"] == THU


def test_35_drag_to_front_shifts_the_chain() -> None:
    """§35: dragging X to the front is the only thing that moves the planned work."""
    before = schedule([*ABC_QUEUE, item("X", 6 * H, 4)], calendar(), MON)
    after = schedule([*ABC_QUEUE, item("X", 6 * H, "0.5")], calendar(), MON)

    assert by_day(after) == {
        MON: [("X", 6 * H), ("A", 2 * H)],
        TUE: [("A", 6 * H), ("B", 2 * H)],
        WED: [("B", 6 * H), ("C", 2 * H)],
        THU: [("C", 6 * H)],
    }
    assert {c.task_id: c.shift_days for c in diff_plans(before, after)} == {
        "A": 1,
        "B": 1,
        "C": 1,
        "X": -3,
    }


def test_32_2_3_task_x_12h_moved_to_the_front() -> None:
    """§32.2.3: the exact table of a 12h task dragged to the head of the queue."""
    result = schedule([*ABC_QUEUE, item("X", 12 * H, "0.5")], calendar(), MON)

    assert by_day(result) == {
        MON: [("X", 8 * H)],
        TUE: [("X", 4 * H), ("A", 4 * H)],
        WED: [("A", 4 * H), ("B", 4 * H)],
        THU: [("B", 4 * H), ("C", 4 * H)],
        FRI: [("C", 4 * H)],
    }


def test_36_leave_makes_a_fixed_date_impossible() -> None:
    """§36: a 4h leave on Thursday; the hard constraint reports the missing capacity."""
    result = schedule(BASE_QUEUE, calendar(exceptions={THU: 4 * H}), MON)

    days = by_day(result)
    assert days[THU] == [("T3", 1 * H), ("T4", 3 * H)]
    assert days[FRI] == [("T4", 3 * H), ("T5", 3 * H)]

    assert result.has_conflicts
    conflict = result.conflicts[0]
    assert conflict.type == ReasonType.FIXED_DATE_CONFLICT
    assert conflict.task_id == "T5"
    assert conflict.minutes == 3 * H  # "Missing capacity: 3h"
    assert "Missing capacity: 3h." in conflict.message


def test_37_effort_increase_pushes_the_rest_forward() -> None:
    """§37/§46.3: raising B from 8h to 12h stretches the glass, C slips by a day."""
    before = schedule(ABC_QUEUE, calendar(), MON)
    after = schedule(
        [item("A", 8 * H, 1), item("B", 12 * H, 2), item("C", 8 * H, 3)], calendar(), MON
    )

    assert by_day(after) == {
        MON: [("A", 8 * H)],
        TUE: [("B", 8 * H)],
        WED: [("B", 4 * H), ("C", 4 * H)],
        THU: [("C", 4 * H)],
    }
    assert {c.task_id: c.shift_days for c in diff_plans(before, after)} == {"B": 1, "C": 1}


def test_39_moved_meeting_is_asymmetric() -> None:
    """§39: the meeting moves from Monday to Thursday.

    Recovered Monday capacity pulls nothing back (R6); the Thursday reduction
    redistributes the remaining work forward. Days already planned before the
    change stay locked, which is what makes the asymmetry real.
    """
    before = schedule(BASE_QUEUE, calendar(busy={MON: 2 * H}), MON)
    frozen = [locked(s.task_id, s.date, s.minutes) for s in before.segments if s.date < THU]
    remaining = [
        item("T3", 3 * H, 3, title="QC integration"),
        item("T4", 6 * H, 4, title="Manager export"),
        item("T5", 3 * H, 5, title="Release cliente", fixed=THU),
    ]
    after = schedule(remaining, calendar(busy={THU: 2 * H}), THU, locked_segments=frozen)

    days = by_day(after)
    assert days[MON] == [("T1", 5 * H), ("T2", 1 * H)]  # not pulled back
    assert days[THU] == [("T3", 3 * H), ("T4", 3 * H)]  # 2h less than before
    assert days[FRI] == [("T4", 3 * H), ("T5", 3 * H)]
    assert all(c.shift_days >= 0 for c in diff_plans(before, after))

    # A naive full recompute would compact Monday — precisely what R6 forbids.
    naive = schedule(BASE_QUEUE, calendar(busy={THU: 2 * H}), MON)
    assert by_day(naive)[MON] == [("T1", 5 * H), ("T2", 3 * H)]


def test_40_cancelled_meeting_recovers_capacity_without_compaction() -> None:
    """§40: capacity recovered, no auto compaction, no auto reorder."""
    before = schedule(BASE_QUEUE, calendar(busy={MON: 2 * H}), MON)
    frozen = [locked(s.task_id, s.date, s.minutes) for s in before.segments]
    after = schedule([], calendar(), MON, locked_segments=frozen)

    assert by_day(after) == by_day(before)
    assert diff_plans(before, after) == []
    assert calendar().available(MON) == 8 * H  # the freed capacity is visible


def test_46_2_completed_task_compacts_forward() -> None:
    """§46.2: A completed after 5h; B and C slide forward keeping the queue order."""
    before = schedule(ABC_QUEUE, calendar(), MON)
    assert by_day(before) == {MON: [("A", 8 * H)], TUE: [("B", 8 * H)], WED: [("C", 8 * H)]}

    after = schedule(
        [item("B", 8 * H, 2), item("C", 8 * H, 3)],
        calendar(),
        MON,
        locked_segments=[locked("A", MON, 5 * H)],
    )

    assert by_day(after) == {
        MON: [("A", 5 * H), ("B", 3 * H)],
        TUE: [("B", 5 * H), ("C", 3 * H)],
        WED: [("C", 5 * H)],
    }
    assert after.delivery_dates == {"A": MON, "B": TUE, "C": WED}


def test_32_2_2_twelve_hours_split_over_two_days() -> None:
    """§32.2.2: today and tomorrow are full, a 12h task lands 8h + 4h later."""
    full = [locked("done", MON, 8 * H), locked("done", TUE, 8 * H)]
    result = schedule([item("X", 12 * H, 1)], calendar(), MON, locked_segments=full)

    assert by_day(result)[WED] == [("X", 8 * H)]
    assert by_day(result)[THU] == [("X", 4 * H)]
    assert result.delivery_dates["X"] == THU


def test_fixed_date_met_produces_no_conflict() -> None:
    queue = [*BASE_QUEUE[:4], item("T5", 3 * H, 5, title="Release cliente", fixed=FRI)]
    result = schedule(queue, calendar(), MON)

    assert result.delivery_dates["T5"] == FRI
    assert not result.has_conflicts


def test_target_date_only_warns() -> None:
    result = schedule([item("A", 16 * H, 1, target=MON)], calendar(), MON)

    assert not result.has_conflicts
    assert [w.type for w in result.warnings] == [ReasonType.TARGET_MISSED]


def test_every_violated_fixed_date_gets_its_own_conflict() -> None:
    """§32.2.8: one conflict per violated fixed date, not just the first."""
    queue = [
        item("A", 16 * H, 1, fixed=MON),
        item("B", 8 * H, 2, fixed=TUE),
        item("C", 8 * H, 3, fixed=FRI),
    ]
    result = schedule(queue, calendar(), MON)

    assert [c.task_id for c in result.conflicts] == ["A", "B"]


def test_small_hole_is_skipped_but_a_small_task_fits() -> None:
    """§32.2.8: holes under 30 minutes are not filled, unless the task fits whole."""
    tiny_left = [locked("busy", MON, 8 * H - 20)]
    big = schedule([item("X", 4 * H, 1)], calendar(), MON, locked_segments=tiny_left)
    assert by_day(big)[MON] == [("busy", 8 * H - 20)]
    assert big.delivery_dates["X"] == TUE

    small = schedule([item("Y", 10, 1)], calendar(), MON, locked_segments=tiny_left)
    assert by_day(small)[MON] == [("busy", 8 * H - 20), ("Y", 10)]


def test_weekend_is_skipped() -> None:
    result = schedule([item("A", 16 * H, 1)], calendar(), FRI)

    assert by_day(result) == {FRI: [("A", 8 * H)], NEXT_MON: [("A", 8 * H)]}
    assert SAT not in by_day(result)


def test_unschedulable_when_there_is_no_capacity_at_all() -> None:
    empty = calendar(exceptions={})
    dead = type(empty)(weekly={}, exceptions={}, busy={})
    result = schedule([item("A", 60, 1)], dead, MON)

    assert [c.type for c in result.conflicts] == [ReasonType.UNSCHEDULABLE]
    assert result.segments == ()
    assert isinstance(result.conflicts[0].minutes, int)
    assert result.conflicts[0].date is None or isinstance(result.conflicts[0].date, date)
