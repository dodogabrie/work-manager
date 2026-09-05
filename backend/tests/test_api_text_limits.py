"""Limiti dei campi di testo.

Una descrizione serve a riprendere in mano il lavoro fra due settimane, non a
documentarlo: senza un tetto diventa illeggibile proprio nel posto da cui la si
guarda, cioè la riga della coda.
"""

from __future__ import annotations

import pytest

from app.schemas import DESCRIPTION_MAX, NOTES_MAX, TITLE_MAX


def _add(owner, **fields):
    return owner.post("/api/inbox/quick-add", json={"title": "T", **fields})


def test_a_description_within_the_limit_is_kept(owner):
    text = "x" * DESCRIPTION_MAX
    task = _add(owner, description=text).json()
    assert task["description"] == text


def test_a_description_over_the_limit_is_rejected(owner):
    assert _add(owner, description="x" * (DESCRIPTION_MAX + 1)).status_code == 422


def test_internal_notes_have_their_own_larger_limit(owner):
    assert _add(owner, internal_notes="x" * NOTES_MAX).status_code == 201
    assert _add(owner, internal_notes="x" * (NOTES_MAX + 1)).status_code == 422


def test_a_title_over_the_limit_is_rejected(owner):
    assert owner.post(
        "/api/inbox/quick-add", json={"title": "x" * (TITLE_MAX + 1)}
    ).status_code == 422


@pytest.mark.parametrize("title", ["", "   "])
def test_an_empty_title_is_rejected(owner, title):
    """§6.2: il titolo è l'unico campo obbligatorio, quindi deve esserci davvero."""
    assert owner.post("/api/inbox/quick-add", json={"title": title}).status_code == 422


def test_the_same_limits_apply_to_an_update(owner):
    task = _add(owner).json()

    assert owner.patch(
        f"/api/tasks/{task['id']}", json={"description": "x" * (DESCRIPTION_MAX + 1)}
    ).status_code == 422
    assert owner.patch(
        f"/api/tasks/{task['id']}", json={"description": "va bene"}
    ).status_code == 200
