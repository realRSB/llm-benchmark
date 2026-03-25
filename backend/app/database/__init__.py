# Database: engine, tables, and benchmark persistence helpers.

from app.database.db import (
    SessionLocal,
    get_database_url,
    get_engine,
    get_session,
    get_session_factory,
    init_db,
)
from app.database.repository import get_latest_benchmark_run, save_benchmark_run

__all__ = [
    "SessionLocal",
    "get_database_url",
    "get_engine",
    "get_session",
    "get_session_factory",
    "init_db",
    "get_latest_benchmark_run",
    "save_benchmark_run",
]


def __getattr__(name: str):
    # Lazy engine: importing `engine` does not connect until first use.
    if name == "engine":
        return get_engine()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
