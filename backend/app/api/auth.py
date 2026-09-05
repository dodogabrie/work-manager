"""Login owner: password singola argon2 + cookie di sessione (§32, §28)."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request, Response

from ..config import settings
from ..schemas import LoginIn, SessionView
from ..security import issue_session, verify_password
from .deps import Owner, clear_session_cookie, set_session_cookie

router = APIRouter(prefix="/api/auth", tags=["auth"])

#: §28: rate limiting sul login. In memoria e per processo — l'app è
#: single-owner e gira in un processo solo; se un giorno servissero più worker,
#: qui va una tabella o un Redis.
# ponytail: finestra scorrevole in RAM, niente store esterno.
RATE_LIMIT = 10
RATE_WINDOW = 60.0
_attempts: dict[str, deque[float]] = defaultdict(deque)


def _check_rate(client: str) -> None:
    now = time.monotonic()
    hits = _attempts[client]
    while hits and now - hits[0] > RATE_WINDOW:
        hits.popleft()
    if len(hits) >= RATE_LIMIT:
        raise HTTPException(429, "too many login attempts, try again later")
    hits.append(now)


@router.post("/login", response_model=SessionView)
def login(payload: LoginIn, request: Request, response: Response) -> SessionView:
    _check_rate(request.client.host if request.client else "unknown")
    stored = settings.resolved_owner_password_hash
    if not stored or not verify_password(payload.password, stored):
        raise HTTPException(401, "invalid credentials")
    set_session_cookie(response, issue_session("owner"))
    return SessionView(subject="owner")


@router.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=SessionView)
def me(principal: Owner) -> SessionView:
    return SessionView(subject=principal.name)
