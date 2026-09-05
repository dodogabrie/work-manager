"""Ordine di lettura del piano (§33, R10).

Dentro un giorno i segmenti devono seguire la coda. Ordinare per task_id — un
UUID — darebbe una sequenza casuale e per giunta diversa fra due letture dello
stesso piano, che è esattamente ciò che R10 esclude.
"""

from __future__ import annotations

from app.models import TaskStatus
from app.services import planning, proposals, tasks

from .conftest import MON


def _plan_three(session):
    """Tre task da 5h, 3h e 8h: il primo giorno ne contiene due."""
    created = []
    for title, minutes in (("A", 300), ("B", 180), ("C", 480)):
        task = tasks.quick_add(session, title, planning_effort_minutes=minutes)
        proposals.approve(
            session,
            tasks.change_status(session, task.id, TaskStatus.PLANNED, horizon_start=MON).id,
        )
        created.append(task)
    return created


def test_segments_within_a_day_follow_the_queue(session):
    _plan_three(session)

    first_day = [s for s in planning.current_plan(session).segments if s.date == MON]

    assert [s.minutes for s in first_day] == [300, 180]


def test_reading_the_plan_twice_gives_the_same_order(session):
    _plan_three(session)

    first = [(s.task_id, s.date, s.minutes) for s in planning.current_plan(session).segments]
    second = [(s.task_id, s.date, s.minutes) for s in planning.current_plan(session).segments]

    assert first == second


def test_reordering_the_queue_reorders_the_day(session):
    a, b, _ = _plan_three(session)

    # B in testa alla coda, davanti ad A: il giorno si rilegge nell'ordine nuovo.
    # `after_id` è il vicino che seguirà il task spostato.
    proposals.approve(
        session,
        tasks.move_in_queue(session, b.id, MON, after_id=a.id).id,
    )

    first_day = [s for s in planning.current_plan(session).segments if s.date == MON]
    assert [s.minutes for s in first_day] == [180, 300]
