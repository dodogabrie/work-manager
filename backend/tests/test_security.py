"""Percorso di autenticazione: se si rompe silenziosamente, l'app resta aperta."""

from app.security import (
    generate_token,
    hash_password,
    hash_token,
    issue_session,
    read_session,
    tokens_match,
    verify_password,
)


def test_password_roundtrip():
    h = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", h)
    assert not verify_password("wrong", h)


def test_password_hash_is_salted():
    assert hash_password("same") != hash_password("same")


def test_verify_password_rejects_garbage_hash():
    assert not verify_password("x", "not-a-hash")


def test_token_is_high_entropy_and_unique():
    tokens = {generate_token() for _ in range(100)}
    assert len(tokens) == 100
    assert all(len(t) >= 43 for t in tokens)


def test_token_matching():
    t = generate_token()
    assert tokens_match(t, hash_token(t))
    assert not tokens_match(generate_token(), hash_token(t))


def test_session_roundtrip():
    assert read_session(issue_session("owner")) == "owner"


def test_tampered_session_is_rejected():
    cookie = issue_session("owner")
    assert read_session(cookie[:-4] + "aaaa") is None
    assert read_session("garbage") is None
