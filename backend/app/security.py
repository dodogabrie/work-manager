"""Password owner, token e sessione (§28).

Regole: la password owner è hashata con argon2; i token (API, share link, feed
ICS) sono generati con secrets e salvati SOLO come hash — vengono mostrati in
chiaro una volta sola, alla creazione, e non sono più recuperabili.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from itsdangerous import BadSignature, URLSafeTimedSerializer

from .config import settings

_hasher = PasswordHasher()
_SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 giorni


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, ValueError):
        return False


def generate_token() -> str:
    """Token ad alta entropia per API, share link e feed ICS (§28)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """SHA-256 e non argon2: i token hanno già 256 bit di entropia, quindi non
    sono forzabili a dizionario, e vengono verificati a ogni richiesta — un KDF
    lento qui sarebbe solo un costo per richiesta."""
    return hashlib.sha256(token.encode()).hexdigest()


def tokens_match(token: str, token_hash: str) -> bool:
    return hmac.compare_digest(hash_token(token), token_hash)


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret, salt="work-planner-session")


def issue_session(subject: str) -> str:
    return _serializer().dumps({"sub": subject})


def read_session(cookie: str) -> str | None:
    try:
        data = _serializer().loads(cookie, max_age=_SESSION_MAX_AGE)
    except BadSignature:
        return None
    return data.get("sub")
