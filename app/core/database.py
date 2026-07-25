from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from .config import settings


def _build_connect_args() -> dict[str, object]:
    if settings.is_sqlite:
        return {"check_same_thread": False}

    return {}


engine = create_engine(
    settings.database_url,
    echo=settings.sql_echo,
    pool_pre_ping=not settings.is_sqlite,
    connect_args=_build_connect_args(),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

