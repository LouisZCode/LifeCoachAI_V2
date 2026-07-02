"""SQLite engine, session factory, and FastAPI dependency."""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(
    f"sqlite:///{settings.data_dir / 'lifecoach.db'}",
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _enable_foreign_keys(dbapi_connection, _record) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    from app import models  # noqa: F401 — register tables on Base

    Base.metadata.create_all(engine)
    _migrate(engine)


def _migrate(engine) -> None:
    """Tiny additive migrations — create_all only creates missing tables,
    it never adds columns to existing ones."""
    from sqlalchemy import text

    with engine.begin() as conn:
        columns = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(sessions)")
        }
        if "audio_source" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE sessions ADD COLUMN audio_source VARCHAR(20)"
            )
        # A recording only lives in backend memory — after a restart any
        # session stuck in "recording" holds no audio and must start over.
        conn.execute(
            text("UPDATE sessions SET status='new' WHERE status='recording'")
        )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
