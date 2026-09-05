"""Manager View e feed ICS: le due superfici accessibili con un token nell'URL (§5.2, §18).

Entrambe sono read-only e non vedono mai un modello Task completo: la Manager
View passa da TaskManagerView (§27), il feed ICS espone solo titolo e blocco
temporale.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select

from ..config import settings
from ..integrations.ics_out import FeedSegment, build_feed
from ..models import ManagerShareLink, PlanningSegment, Task
from ..schemas import ShareLinkCreatedView, ShareLinkIn, ShareLinkView, TaskManagerView
from ..security import generate_token, hash_token
from ..services.planning import TZ
from .deps import DbSession, Owner, resolve_share_link

router = APIRouter(tags=["share"])

#: Finestra del feed ICS e della Manager View. Il passato recente serve a dare
#: contesto, il futuro è quello che interessa davvero.
PAST_DAYS = 30
FUTURE_DAYS = 120


# ---------------------------------------------------------------- gestione link (owner)

@router.get("/api/share-links", response_model=list[ShareLinkView])
def list_links(session: DbSession, principal: Owner):
    return list(
        session.scalars(select(ManagerShareLink).order_by(ManagerShareLink.created_at.desc()))
    )


@router.post("/api/share-links", response_model=ShareLinkCreatedView, status_code=201)
def create_link(payload: ShareLinkIn, session: DbSession, principal: Owner):
    """§28: il token in chiaro esiste solo in questa risposta; in DB c'è l'hash."""
    token = generate_token()
    link = ManagerShareLink(
        label=payload.label,
        kind=payload.kind,
        token_hash=hash_token(token),
        expires_at=payload.expires_at,
    )
    session.add(link)
    session.commit()
    path = f"/calendar/{token}.ics" if payload.kind == "ics" else f"/share/{token}"
    return ShareLinkCreatedView(
        **ShareLinkView.model_validate(link).model_dump(),
        token=token,
        url=f"{settings.public_base_url.rstrip('/')}{path}",
    )


@router.delete("/api/share-links/{link_id}", response_model=ShareLinkView)
def revoke_link(link_id: uuid.UUID, session: DbSession, principal: Owner):
    """§5.2: revoca, non cancellazione — il link resta tracciabile nella history."""
    link = session.get(ManagerShareLink, link_id)
    if link is None:
        raise HTTPException(404, "share link not found")
    link.revoked_at = datetime.now(UTC)
    session.commit()
    return link


# ---------------------------------------------------------------- superfici pubbliche

def _window(day: date) -> tuple[date, date]:
    return day - timedelta(days=PAST_DAYS), day + timedelta(days=FUTURE_DAYS)


def _planned(session, start: date, end: date) -> dict[uuid.UUID, list[PlanningSegment]]:
    grouped: dict[uuid.UUID, list[PlanningSegment]] = {}
    rows = session.scalars(
        select(PlanningSegment)
        .where(PlanningSegment.day >= start, PlanningSegment.day <= end)
        .order_by(PlanningSegment.day)
    )
    for row in rows:
        grouped.setdefault(row.task_id, []).append(row)
    return grouped


@router.get("/api/share/{token}/planning", response_model=list[TaskManagerView])
def manager_planning(token: str, session: DbSession) -> list[TaskManagerView]:
    """§5.2 + §27: solo TaskManagerView, mai il modello Task."""
    resolve_share_link(session, token, kind="manager")
    start, end = _window(datetime.now(TZ).date())
    grouped = _planned(session, start, end)
    if not grouped:
        return []
    out = []
    for task in session.scalars(select(Task).where(Task.id.in_(grouped))):
        if task.deleted_at is None:
            out.append(TaskManagerView.of(task, grouped[task.id]))
    out.sort(key=lambda t: (t.allocation_start or date.max, t.title))
    return out


@router.get("/calendar/{token}.ics")
def calendar_feed(token: str, session: DbSession) -> Response:
    """§18: feed sottoscrivibile da Outlook/Google — nessuna sessione, solo il token."""
    link = resolve_share_link(session, token, kind="ics")
    start, end = _window(datetime.now(TZ).date())
    grouped = _planned(session, start, end)
    segments: list[FeedSegment] = []
    tasks = session.scalars(select(Task).where(Task.id.in_(grouped))) if grouped else []
    for task in tasks:
        if task.deleted_at is not None:
            continue
        for seg in grouped[task.id]:
            segments.append(FeedSegment(
                task_id=str(task.id), title=task.title, day=seg.day, minutes=seg.minutes,
                project_name=task.project.name if task.project else None,
            ))
    body = build_feed(segments, tz=settings.tz, calendar_name=link.label)
    return Response(body, media_type="text/calendar; charset=utf-8")
