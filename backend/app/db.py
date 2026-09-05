"""Sessione SQLAlchemy. Sincrona di proposito: le transazioni di approvazione
usano SELECT ... FOR UPDATE (§26) e il carico è quello di un'app personale."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
