"""§32.2.7 / R10: same state and input -> identical result."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date

from app.domain.diff import diff_plans
from app.domain.models import ScheduleResult
from app.domain.scheduler import schedule
from tests.helpers import MON, THU, H, by_day, calendar, item, locked

QUEUE = [
    item("T1", 5 * H, 1, title="Fix MAG import"),
    item("T2", 12 * H, 2, title="RAW processing API"),
    item("T3", 8 * H, 3, title="QC integration"),
    item("T4", 6 * H, 4, title="Manager export", target=date(2026, 1, 7)),
    item("T5", 3 * H, 5, title="Release cliente", fixed=THU),
]
LOCKED = [locked("T0", MON, 60)]


def dump(result: ScheduleResult) -> str:
    return json.dumps(
        {
            "segments": [asdict(s) for s in result.segments],
            "delivery_dates": result.delivery_dates,
            "reasons": [asdict(r) for r in result.reasons],
        },
        default=str,
        sort_keys=True,
    )


def test_same_input_same_output() -> None:
    cal = calendar(exceptions={date(2026, 1, 9): 4 * H}, busy={MON: 2 * H})
    first = schedule(QUEUE, cal, MON, locked_segments=LOCKED)
    second = schedule(QUEUE, calendar(exceptions={date(2026, 1, 9): 4 * H}, busy={MON: 2 * H}),
                      MON, locked_segments=list(LOCKED))

    assert dump(first) == dump(second)
    assert diff_plans(first, second) == []


def test_queue_input_order_does_not_matter() -> None:
    """§32.2.8 tie-breaking gives a total order: only queue_position decides."""
    forward = schedule(QUEUE, calendar(), MON)
    shuffled = schedule(list(reversed(QUEUE)), calendar(), MON)

    assert dump(forward) == dump(shuffled)


def test_repeated_simulation_is_stable() -> None:
    cal = calendar()
    dumps = {dump(schedule(QUEUE, cal, MON)) for _ in range(5)}

    assert len(dumps) == 1


def test_rescheduling_its_own_output_is_a_fixed_point() -> None:
    """Re-running the scheduler over the same queue reproduces the same plan."""
    first = schedule(QUEUE, calendar(), MON)
    again = schedule(QUEUE, calendar(), MON)

    assert by_day(first) == by_day(again)
