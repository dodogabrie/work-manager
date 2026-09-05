"""Integrazioni calendario in ingresso (§25, §32.18).

Router sottile: nessuna regola qui. Decidere se un sync deve produrre una
proposal è responsabilità di services.calendar_sync (§29).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from ..schemas import (
    CalendarConnectionIn,
    CalendarConnectionPatchIn,
    CalendarConnectionView,
    ProposalView,
    SyncResultView,
)
from ..services import calendar_sync as service
from .deps import Caller, DbSession, Today

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


@router.get("", response_model=list[CalendarConnectionView])
def list_integrations(session: DbSession, principal: Caller):
    return service.list_connections(session)


@router.post("/calendars", response_model=CalendarConnectionView, status_code=201)
def add_calendar(payload: CalendarConnectionIn, session: DbSession, principal: Caller):
    return service.add_connection(session, payload.name, payload.ics_url, payload.enabled)


@router.patch("/calendars/{connection_id}", response_model=CalendarConnectionView)
def patch_calendar(
    connection_id: uuid.UUID, payload: CalendarConnectionPatchIn,
    session: DbSession, principal: Caller,
):
    return service.update_connection(
        session, connection_id, **payload.model_dump(exclude_unset=True)
    )


@router.delete("/calendars/{connection_id}", response_model=CalendarConnectionView)
def delete_calendar(connection_id: uuid.UUID, session: DbSession, principal: Caller):
    return service.remove_connection(session, connection_id)


@router.post("/calendars/{connection_id}/sync", response_model=SyncResultView)
def sync_calendar(
    connection_id: uuid.UUID, session: DbSession, principal: Caller, day: Today
) -> SyncResultView:
    """Sync manuale. Lo stesso codice del job periodico (§29)."""
    result = service.sync_connection(session, service.get_connection(session, connection_id), day)
    return SyncResultView(
        connection=CalendarConnectionView.model_validate(result.connection),
        events_upserted=result.upserted,
        events_cancelled=result.cancelled,
        proposal=ProposalView.model_validate(result.proposal) if result.proposal else None,
    )
