"""Database engine, session, and base configuration."""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def get_db_path() -> Path:
    """Get the database file path."""
    data_dir = Path(os.environ.get("BOKHALD_DATA_DIR", Path.home() / ".local" / "share" / "bokhald"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "bokhald.db"


def get_engine(db_path: Path | None = None):
    """Create and return a SQLAlchemy engine."""
    if db_path is None:
        db_path = get_db_path()
    return create_engine(f"sqlite:///{db_path}", echo=False)


def get_session_factory(engine=None) -> sessionmaker[Session]:
    """Create a session factory."""
    if engine is None:
        engine = get_engine()
    return sessionmaker(bind=engine)
