"""API token per Claude e altri client REST (§5.3, §28)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..models import ApiToken
from ..schemas import ApiTokenCreatedView, ApiTokenIn, ApiTokenView
from ..security import generate_token, hash_token
from .deps import DbSession, Owner

router = APIRouter(prefix="/api/tokens", tags=["tokens"])


@router.get("", response_model=list[ApiTokenView])
def list_tokens(session: DbSession, principal: Owner):
    return list(session.scalars(select(ApiToken).order_by(ApiToken.created_at.desc())))


@router.post("", response_model=ApiTokenCreatedView, status_code=201)
def create_token(payload: ApiTokenIn, session: DbSession, principal: Owner):
    """Il token in chiaro è mostrato una volta sola: in DB c'è solo l'hash (§28)."""
    token = generate_token()
    row = ApiToken(label=payload.label, token_hash=hash_token(token), scopes=payload.scopes)
    session.add(row)
    session.commit()
    return ApiTokenCreatedView(**ApiTokenView.model_validate(row).model_dump(), token=token)


@router.delete("/{token_id}", response_model=ApiTokenView)
def revoke_token(token_id: uuid.UUID, session: DbSession, principal: Owner):
    row = session.get(ApiToken, token_id)
    if row is None:
        raise HTTPException(404, "api token not found")
    row.revoked_at = datetime.now(UTC)
    session.commit()
    return row
