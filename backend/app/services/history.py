"""Audit log e undo/redo non lineare (§23).

L'undo non ricarica uno snapshot: applica l'operazione inversa allo stato
corrente (§23.3-23.4). Se quello stato è cambiato, l'inversa può richiedere una
proposal, produrre conflitti o essere impossibile: gli esiti sono valori di
ritorno, non eccezioni (il flusso normale li prevede tutti).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Action, PlanningProposal, ProposalKind, ProposalOrigin
from . import proposals

#: §23.6: la generazione di un report e gli eventi arrivati dal calendario
#: esterno non sono annullabili. Del calendario si annulla l'effetto sul piano,
#: cioè la proposal che è stata approvata, non l'evento in sé.
NON_REVERSIBLE_ACTIONS = frozenset({"REPORT_GENERATED", "CALENDAR_EVENT_SYNCED"})

Status = Literal["applied", "proposal", "conflict", "impossible"]


@dataclass(frozen=True, slots=True)
class UndoOutcome:
    status: Status
    action: Action | None = None
    proposal: PlanningProposal | None = None
    message: str = ""


def record(
    session: Session,
    action_type: str,
    origin: ProposalOrigin = ProposalOrigin.UI,
    actor: str | None = None,
    entities: dict[str, Any] | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    inverse_of_id: uuid.UUID | None = None,
) -> Action:
    """Registra un'azione che non passa dal piano (§23.1)."""
    action = Action(
        action_type=action_type,
        origin=origin,
        actor=actor,
        created_at=datetime.now(UTC),
        entities=entities or {},
        before=before,
        after=after,
        reversible=action_type not in NON_REVERSIBLE_ACTIONS,
        inverse_of_id=inverse_of_id,
    )
    session.add(action)
    session.flush()
    return action


def history(session: Session, limit: int = 50) -> list[Action]:
    return list(
        session.scalars(select(Action).order_by(Action.created_at.desc()).limit(limit))
    )


def undo(session: Session, action_id: uuid.UUID, horizon_start: date) -> UndoOutcome:
    action = session.get(Action, action_id)
    if action is None:
        return UndoOutcome("impossible", message=f"action {action_id} not found")
    if not action.reversible:
        return UndoOutcome("impossible", action=action,
                           message=f"{action.action_type} is not reversible (§23.6)")
    if action.undone:
        return UndoOutcome("impossible", action=action, message="action is already undone")
    intent = _payload(action.before)
    if not intent:
        return UndoOutcome("impossible", action=action, message="nothing to restore")
    intent["inverse_of"] = str(action.id)
    return _run(session, action, intent, horizon_start, ProposalKind.UNDO, "UNDO")


def redo(session: Session, action_id: uuid.UUID, horizon_start: date) -> UndoOutcome:
    """§23.5: riapplica semanticamente l'azione allo stato corrente, non ripristina dati."""
    action = session.get(Action, action_id)
    if action is None:
        return UndoOutcome("impossible", message=f"action {action_id} not found")
    if not action.reversible:
        return UndoOutcome("impossible", action=action,
                           message=f"{action.action_type} is not reversible (§23.6)")
    intent = _payload(action.after)
    if not intent:
        return UndoOutcome("impossible", action=action, message="nothing to reapply")
    intent["redo_of"] = str(action.id)
    return _run(session, action, intent, horizon_start, ProposalKind.REDO, "REDO")


def _run(
    session: Session,
    action: Action,
    intent: dict[str, Any],
    horizon_start: date,
    kind: ProposalKind,
    prefix: str,
) -> UndoOutcome:
    if action.snapshot_id is not None:
        # Tocca il piano: non si applica, si propone (§23.3).
        proposal = proposals.propose(
            session, kind, action.origin, intent, horizon_start, action.actor
        )
        session.commit()
        if proposal.simulation["conflicts"]:
            return UndoOutcome(
                "conflict", action=action, proposal=proposal,
                message="; ".join(c["message"] for c in proposal.simulation["conflicts"]),
            )
        return UndoOutcome("proposal", action=action, proposal=proposal)

    proposals.apply_intent(session, intent)
    inverse = record(
        session,
        action_type=f"{prefix}:{action.action_type}",
        origin=action.origin,
        actor=action.actor,
        entities=action.entities,
        before=action.after,
        after=action.before,
        inverse_of_id=action.id,
    )
    action.undone = prefix == "UNDO"
    session.commit()
    return UndoOutcome("applied", action=inverse)


def _payload(data: dict[str, Any] | None) -> dict[str, Any]:
    if not data:
        return {}
    return {k: v for k, v in data.items() if k in ("tasks", "capacity", "completed") and v}
