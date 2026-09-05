"""Dati dei report (§20, §21).

I report sono destinati al manager, quindi passano dagli stessi campi della
Manager View: `TaskManagerView` è l'unica porta d'ingresso dei task (§27).
Niente note interne, niente stato READY, niente tempo effettivo.

Qui si calcola anche la geometria delle barre (offset e larghezza in %): il
template deve solo disegnare, non fare aritmetica.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import PlanningProposal, PlanningSegment, Task
from ..schemas import TaskManagerView
from ..services import planning as service

#: Etichette leggibili degli stati pubblici (§5.2: READY non esiste, è IN_PROGRESS).
STATUS_LABEL: dict[str, str] = {
    "PLANNED": "Pianificato",
    "IN_PROGRESS": "In corso",
    "DELIVERED": "Consegnato",
    "BLOCKED": "Bloccato",
    "CANCELLED": "Annullato",
    "ARCHIVED": "Archiviato",
}

#: §12: il tipo di proposal, detto in una riga comprensibile a un manager.
KIND_LABEL: dict[str, str] = {
    "TASK_PLANNED": "Nuova attività da pianificare",
    "QUEUE_REORDER": "Riordino delle priorità",
    "EFFORT_CHANGE": "Revisione dell'effort stimato",
    "TASK_COMPLETED": "Attività completata",
    "TASK_CANCELLED": "Attività annullata",
    "CAPACITY_CHANGE": "Variazione di disponibilità",
    "CALENDAR_CHANGE": "Variazione di calendario",
    "UNDO": "Annullamento di una modifica",
    "REDO": "Ripristino di una modifica",
}

DEFAULT_DAYS = 28


def _segments_by_task(
    session: Session, task_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[PlanningSegment]]:
    """Tutti i segmenti dei task indicati, senza limiti di finestra: la data di
    consegna è quella vera, non quella tagliata dall'intervallo del report."""
    grouped: dict[uuid.UUID, list[PlanningSegment]] = {}
    if not task_ids:
        return grouped
    rows = session.scalars(
        select(PlanningSegment)
        .where(PlanningSegment.task_id.in_(task_ids))
        .order_by(PlanningSegment.day)
    )
    for row in rows:
        grouped.setdefault(row.task_id, []).append(row)
    return grouped


def _visible_tasks(session: Session, start: date, end: date) -> list[TaskManagerView]:
    window = session.scalars(
        select(PlanningSegment.task_id)
        .where(PlanningSegment.day >= start, PlanningSegment.day <= end)
        .distinct()
    )
    ids = list(window)
    full = _segments_by_task(session, ids)
    out = [
        TaskManagerView.of(task, full.get(task.id, []))
        for task in session.scalars(select(Task).where(Task.id.in_(ids)))
        if task.deleted_at is None
    ]
    out.sort(key=lambda t: (t.allocation_start or date.max, t.title))
    return out


def _bar(start: date, end: date, first: date | None, last: date | None) -> dict[str, float]:
    """Posizione della barra sull'asse [start, end], in percentuale."""
    span = (end - start).days + 1
    if first is None or last is None:
        return {"offset": 0.0, "width": 0.0}
    left = max(first, start)
    right = min(last, end)
    if right < left:
        return {"offset": 0.0, "width": 0.0}
    return {
        "offset": round((left - start).days / span * 100, 3),
        "width": round(((right - left).days + 1) / span * 100, 3),
    }


def _weeks(session: Session, start: date, end: date) -> list[dict[str, Any]]:
    """Capacità e carico aggregati per settimana (§20).

    Per settimana e non per giorno: un report su un mese diventerebbe una tabella
    di trenta righe che nessuno legge.
    """
    capacity = service.build_capacity(session, start, end)
    planned: dict[date, int] = {}
    for seg in session.scalars(service.segments_query(start, end)):
        planned[seg.day] = planned.get(seg.day, 0) + seg.minutes

    buckets: dict[date, dict[str, Any]] = {}
    day = start
    while day <= end:
        monday = day - timedelta(days=day.weekday())
        week = buckets.setdefault(monday, {"start": monday, "available": 0, "planned": 0})
        week["available"] += capacity.available(day)
        week["planned"] += planned.get(day, 0)
        day += timedelta(days=1)

    weeks = []
    for week in sorted(buckets.values(), key=lambda w: w["start"]):
        available = week["available"]
        weeks.append({
            **week,
            "end": min(week["start"] + timedelta(days=6), end),
            "fill": round(min(week["planned"] / available, 1.0) * 100, 1) if available else 0.0,
            "over": available and week["planned"] > available,
        })
    return weeks


def _projects(tasks: list[TaskManagerView]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for task in tasks:
        name = task.project or "Senza progetto"
        row = grouped.setdefault(
            name, {"name": name, "color": task.project_color or "#6b7280", "minutes": 0, "tasks": 0}
        )
        row["minutes"] += task.planned_effort_minutes
        row["tasks"] += 1
    return sorted(grouped.values(), key=lambda p: -p["minutes"])


def planning_context(
    session: Session,
    start: date,
    end: date,
    *,
    notes: str | None = None,
    title: str = "Piano di lavoro",
) -> dict[str, Any]:
    """§20: intervallo, progetti, task, effort, timeline, consegne, capacità, note."""
    tasks = _visible_tasks(session, start, end)
    rows = [
        {
            "title": task.title,
            "project": task.project or "Senza progetto",
            "color": task.project_color or "#6b7280",
            "minutes": task.planned_effort_minutes,
            "start": task.allocation_start,
            "end": task.allocation_end,
            "delivery": task.delivery_date,
            "status": STATUS_LABEL.get(task.status, task.status),
            "bar": _bar(start, end, task.allocation_start, task.allocation_end),
        }
        for task in tasks
    ]
    return {
        "kind": "planning",
        "title": title,
        "start": start,
        "end": end,
        "generated_at": datetime.now(UTC),
        "axis": _axis(start, end),
        "tasks": rows,
        "projects": _projects(tasks),
        "weeks": _weeks(session, start, end),
        # §20 "note pubbliche": testo scritto dall'owner per il destinatario del
        # report. Le note interne del task non entrano mai qui (§27).
        "notes": notes,
        "total_minutes": sum(r["minutes"] for r in rows),
    }


def _axis(start: date, end: date) -> list[dict[str, Any]]:
    """Tacche settimanali dell'asse temporale."""
    span = (end - start).days + 1
    ticks = []
    day = start - timedelta(days=start.weekday())
    while day <= end:
        if day >= start:
            ticks.append({"day": day, "offset": round((day - start).days / span * 100, 3)})
        day += timedelta(days=7)
    return ticks


def impact_context(
    session: Session, proposal: PlanningProposal, *, notes: str | None = None
) -> dict[str, Any]:
    """§21: prima, nuova richiesta, dopo, effetti.

    I dati arrivano dalla simulazione già calcolata sulla proposal (§12): il
    report non ri-simula nulla.
    """
    changes = proposal.simulation.get("changes", [])
    ids = [uuid.UUID(c["task_id"]) for c in changes]
    known = {
        str(task.id): task
        for task in session.scalars(select(Task).where(Task.id.in_(ids)))
        if task.deleted_at is None
    }

    days = [
        _iso(value)
        for change in changes
        for value in (change["old_start"], change["new_start"],
                      change["old_delivery"], change["new_delivery"])
        if value
    ]
    start = min(days) if days else date.today()
    end = max(days) if days else start

    effects = []
    for change in changes:
        task = known.get(change["task_id"])
        if task is None:
            continue
        old_start, old_end = _iso(change["old_start"]), _iso(change["old_delivery"])
        new_start, new_end = _iso(change["new_start"]), _iso(change["new_delivery"])
        effects.append({
            "title": task.title,
            "project": task.project.name if task.project else "Senza progetto",
            "color": task.project.color if task.project else "#6b7280",
            "old_start": old_start,
            "old_delivery": old_end,
            "new_start": new_start,
            "new_delivery": new_end,
            "shift_days": change["shift_days"],
            "effect": _effect(change["shift_days"], new_end),
            "before_bar": _bar(start, end, old_start, old_end),
            "after_bar": _bar(start, end, new_start, new_end),
        })

    return {
        "kind": "impact",
        "title": "Impatto della richiesta",
        "request": KIND_LABEL.get(str(proposal.kind), str(proposal.kind)),
        "requested_at": proposal.created_at,
        "generated_at": datetime.now(UTC),
        "start": start,
        "end": end,
        "axis": _axis(start, end),
        "effects": effects,
        # §14.1/§14.2: conflitti e warning sono informazione condivisibile —
        # dicono al manager se la richiesta è sostenibile.
        "conflicts": [r["message"] for r in proposal.simulation.get("conflicts", [])],
        "warnings": [r["message"] for r in proposal.simulation.get("warnings", [])],
        "notes": notes,
    }


def _effect(shift_days: int, new_delivery: date | None) -> str:
    if shift_days > 0:
        return f"+{shift_days} giorn{'o' if shift_days == 1 else 'i'}"
    if shift_days < 0:
        days = -shift_days
        return f"−{days} giorn{'o' if days == 1 else 'i'}"
    return "consegna invariata" if new_delivery else "riprogrammato"


def _iso(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None
