"""Job in-process (§32: APScheduler, niente Celery/Redis).

Un solo job: il polling dei feed ICS. Non applica nulla al piano — chiama lo
stesso `sync_connection` del sync manuale, che al più deposita una proposal.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from .api.deps import today
from .config import settings
from .db import SessionLocal
from .services import calendar_sync

log = logging.getLogger(__name__)

CALENDAR_SYNC_MINUTES = 15


def sync_calendars() -> None:
    with SessionLocal() as session:
        for result in calendar_sync.sync_all(session, today()):
            if result.error:
                log.warning("calendar sync failed for %s: %s", result.connection.name, result.error)


def start() -> BackgroundScheduler | None:
    """`enable_jobs=False` in test e nei comandi CLI: nessuno scheduler parte."""
    if not settings.enable_jobs:
        return None
    scheduler = BackgroundScheduler(timezone=settings.tz)
    scheduler.add_job(
        sync_calendars, "interval", minutes=CALENDAR_SYNC_MINUTES,
        id="calendar_sync", max_instances=1, coalesce=True,
    )
    scheduler.start()
    return scheduler
