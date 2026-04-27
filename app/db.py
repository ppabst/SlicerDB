"""Database engine and session management.

SQLite-specific knobs:
- WAL mode for better concurrent reads
- Foreign-key enforcement (off by default in SQLite)
"""

from collections.abc import Iterator
from pathlib import Path

from alembic.config import Config
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from alembic import command
from app.config import settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            settings.db_url,
            echo=settings.debug,
            connect_args={"check_same_thread": False},
        )
        _apply_sqlite_pragmas(_engine)
    return _engine


def _apply_sqlite_pragmas(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection, _connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


def init_db() -> None:
    """Create all tables directly from SQLModel metadata.

    Used in tests where we don't want Alembic overhead. Production should call
    `run_migrations()` instead so we stay aligned with the migration history.
    """
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(get_engine())


def run_migrations() -> None:
    """Bring the DB schema up to head. Idempotent."""
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.db_url)
    command.upgrade(cfg, "head")


def get_session() -> Iterator[Session]:
    """FastAPI dependency that yields a database session."""
    with Session(get_engine()) as session:
        yield session
