"""Report PDF/PNG (§20, §21, §25).

Il router è sottile: valida l'intervallo, chiede il contesto al package
`app.reports` e restituisce il file. Nessuna regola di planning qui.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, HTTPException, Response

from .. import reports
from ..models import PlanningProposal
from ..reports.data import DEFAULT_DAYS
from ..schemas import ImpactReportIn, PlanningReportIn
from .deps import Caller, DbSession, Today

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _file(session, context: dict, fmt: reports.Format, params: dict) -> Response:
    content, name = reports.generate(session, context, fmt, params)
    return Response(
        content,
        media_type=reports.MEDIA_TYPES[fmt],
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.post("/planning")
def planning_report(
    payload: PlanningReportIn, session: DbSession, principal: Caller, day: Today
) -> Response:
    start = payload.start or day
    end = payload.end or start + timedelta(days=DEFAULT_DAYS)
    if end < start:
        raise HTTPException(422, "end must not precede start")
    context = reports.planning_context(
        session, start, end, notes=payload.notes, title=payload.title
    )
    return _file(session, context, payload.format, payload.model_dump(mode="json"))


@router.post("/impact")
def impact_report(
    payload: ImpactReportIn, session: DbSession, principal: Caller
) -> Response:
    proposal = session.get(PlanningProposal, payload.proposal_id)
    if proposal is None:
        raise HTTPException(404, "proposal not found")
    context = reports.impact_context(session, proposal, notes=payload.notes)
    return _file(session, context, payload.format, payload.model_dump(mode="json"))
