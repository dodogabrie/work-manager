"""Scrittura della capacità settimanale (§11.2).

È configurazione, non un evento sul piano: non genera proposal. Ma è anche il
numero da cui dipende tutto lo scheduling, quindi i valori assurdi vanno
rifiutati invece di finire silenziosamente nel piano.
"""

from __future__ import annotations


def test_weekly_capacity_roundtrip(owner):
    response = owner.put("/api/capacity/weekly", json={"minutes": {"0": 300, "5": 120}})

    assert response.status_code == 200
    weekly = response.json()["weekly_minutes"]
    assert weekly["0"] == 300
    assert weekly["5"] == 120


def test_days_not_mentioned_keep_their_value(owner):
    """Un aggiornamento parziale non deve azzerare il resto della settimana."""
    owner.put("/api/capacity/weekly", json={"minutes": {"0": 480, "1": 480}})

    weekly = owner.put(
        "/api/capacity/weekly", json={"minutes": {"0": 240}}
    ).json()["weekly_minutes"]

    assert weekly["0"] == 240
    assert weekly["1"] == 480


def test_a_day_longer_than_a_day_is_rejected(owner):
    assert owner.put("/api/capacity/weekly", json={"minutes": {"0": 1441}}).status_code == 422


def test_negative_capacity_is_rejected(owner):
    assert owner.put("/api/capacity/weekly", json={"minutes": {"0": -60}}).status_code == 422


def test_invalid_weekday_is_rejected(owner):
    assert owner.put("/api/capacity/weekly", json={"minutes": {"7": 480}}).status_code == 422


def test_writing_capacity_requires_authentication(client):
    assert client.put("/api/capacity/weekly", json={"minutes": {"0": 480}}).status_code == 401


def test_setting_capacity_does_not_create_a_proposal(owner):
    """§11.2: la capacità standard è configurazione. Il piano viene riverificato
    alla prima simulazione, non ripianificato qui."""
    before = len(owner.get("/api/proposals").json())

    owner.put("/api/capacity/weekly", json={"minutes": {"0": 240}})

    assert len(owner.get("/api/proposals").json()) == before
