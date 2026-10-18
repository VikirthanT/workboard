from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
# Default expire_on_commit: after a command commits, the query that reads the result back must see fresh rows.
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """One session per request. Services commit; an error before commit rolls back on close."""
    with SessionLocal() as db:
        yield db
