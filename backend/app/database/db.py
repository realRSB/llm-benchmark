# SQLAlchemy engine and session factory for benchmark persistence.

from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import Base
from app.env import load_dotenv_if_needed

load_dotenv_if_needed()

_engine: Engine | None = None
_session_factory: sessionmaker | None = None


def get_database_url() -> str:
    # PostgreSQL only, e.g. postgresql+psycopg2://user:pass@localhost:5432/dbname
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Point it at PostgreSQL, e.g. "
            "postgresql+psycopg2://user:pass@localhost:5432/llm_bench"
        )
    scheme = url.split("://", 1)[0].lower() if "://" in url else ""
    if "postgres" not in scheme:
        raise RuntimeError(
            "DATABASE_URL must use PostgreSQL (e.g. postgresql+psycopg2://...)."
        )
    return url


def create_engine_from_url(url: str) -> Engine:
    connect_args: dict[str, str] = {}
    sslmode_env = os.getenv("DATABASE_SSLMODE", "").strip()
    if sslmode_env:
        connect_args["sslmode"] = sslmode_env
    elif "supabase.co" in url and "sslmode" not in url.lower():
        connect_args["sslmode"] = "require"
    return create_engine(url, connect_args=connect_args)


def _create_engine() -> Engine:
    return create_engine_from_url(get_database_url())


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = _create_engine()
    return _engine


def get_session_factory() -> sessionmaker:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    return _session_factory


class _SessionLocalProxy:
    # Callable like sessionmaker: SessionLocal() returns a Session (no engine until then).
    def __call__(self, *args, **kwargs):
        return get_session_factory()(*args, **kwargs)


SessionLocal = _SessionLocalProxy()


def init_db() -> None:
    Base.metadata.create_all(bind=get_engine())


def get_session() -> Generator[Session, None, None]:
    # FastAPI dependency style (optional).
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
