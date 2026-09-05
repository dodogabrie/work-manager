"""Autenticazione e dipendenze condivise (§5, §28).

Tre soggetti, tre meccanismi:
  owner  -> cookie di sessione HttpOnly firmato (§32: password singola argon2)
  API    -> Authorization: Bearer <token>, confrontato per hash (§5.3)
  share  -> token nell'URL, read-only, revocabile e con scadenza (§5.2)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import Depends, Header, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_session
from ..models import ApiToken, ManagerShareLink
from ..security import hash_token, read_session
from ..services.planning import TZ

SESSION_COOKIE = "wp_session"

COOKIE_MAX_AGE = 60 * 60 * 24 * 30


def cookie_secure() -> bool:
    """§28: il cookie è marcato Secure appena l'app è pubblicata in https.

    Valutato a ogni chiamata e non una volta all'import: una costante di modulo
    congelerebbe il valore letto dal `.env` presente al momento dell'import,
    rendendo il comportamento dipendente da dove e come è stato avviato il
    processo — e i test dipendenti dall'ambiente della macchina.
    """
    return settings.public_base_url.startswith("https://")

DbSession = Annotated[Session, Depends(get_session)]


def set_session_cookie(response: Response, value: str) -> None:
    response.set_cookie(
        SESSION_COOKIE, value, httponly=True, samesite="lax",
        secure=cookie_secure(), max_age=COOKIE_MAX_AGE, path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True,
                           samesite="lax", secure=cookie_secure())


def today() -> date:
    """§32.2.8: l'orizzonte parte da oggi come giorno intero, non da "adesso"."""
    return datetime.now(TZ).date()


Today = Annotated[date, Depends(today)]


@dataclass(frozen=True, slots=True)
class Principal:
    kind: Literal["owner", "api"]
    name: str

    @property
    def is_owner(self) -> bool:
        return self.kind == "owner"


def require_owner(request: Request) -> Principal:
    cookie = request.cookies.get(SESSION_COOKIE)
    subject = read_session(cookie) if cookie else None
    if subject is None:
        raise HTTPException(401, "authentication required")
    return Principal("owner", subject)


def _api_token(session: Session, authorization: str | None) -> Principal | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    raw = authorization.split(" ", 1)[1].strip()
    row = session.scalars(
        select(ApiToken).where(
            ApiToken.token_hash == hash_token(raw), ApiToken.revoked_at.is_(None)
        )
    ).first()
    if row is None:
        return None
    row.last_used_at = datetime.now(UTC)  # §28: audit delle operazioni da API
    session.commit()
    return Principal("api", row.label)


def require_api_token(
    session: DbSession, authorization: Annotated[str | None, Header()] = None
) -> Principal:
    principal = _api_token(session, authorization)
    if principal is None:
        raise HTTPException(401, "invalid or revoked API token")
    return principal


def require_owner_or_token(
    request: Request,
    session: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    cookie = request.cookies.get(SESSION_COOKIE)
    subject = read_session(cookie) if cookie else None
    if subject is not None:
        return Principal("owner", subject)
    principal = _api_token(session, authorization)
    if principal is None:
        raise HTTPException(401, "authentication required")
    return principal


Owner = Annotated[Principal, Depends(require_owner)]
Caller = Annotated[Principal, Depends(require_owner_or_token)]


def resolve_share_link(
    session: Session, token: str, kind: str = "manager"
) -> ManagerShareLink:
    """§5.2: un link revocato o scaduto è indistinguibile da uno inesistente.

    404 e non 403 di proposito: non si conferma a un estraneo che il token è
    esistito davvero.
    """
    link = session.scalars(
        select(ManagerShareLink).where(
            ManagerShareLink.token_hash == hash_token(token),
            ManagerShareLink.kind == kind,
        )
    ).first()
    now = datetime.now(UTC)
    if link is None or link.revoked_at is not None:
        raise HTTPException(404, "not found")
    if link.expires_at is not None and _aware(link.expires_at) <= now:
        raise HTTPException(404, "not found")
    link.last_accessed_at = now
    session.commit()
    return link


def _aware(value: datetime) -> datetime:
    """SQLite restituisce datetime naive: normalizza prima di confrontare."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def task_view(principal: Principal):
    """§27: la vista dipende da chi chiede. Claude non vede le note private."""
    from ..schemas import TaskClaudeView, TaskInternalView

    return TaskInternalView if principal.is_owner else TaskClaudeView
