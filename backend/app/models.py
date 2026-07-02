"""SQLAlchemy models: clients and their coaching sessions."""

from datetime import date, datetime, timezone

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(320))
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    sessions: Mapped[list["Session"]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan",
        order_by="Session.session_date.desc(), Session.id.desc()",
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200), default="")
    session_date: Mapped[date]
    notes: Mapped[str] = mapped_column(Text, default="")
    # Lifecycle: new -> recording -> transcribing -> transcribed
    #            -> generating -> docs_ready | error
    # (a failed generation falls back to "transcribed" + error_message,
    # never "error" — the transcript is still good)
    status: Mapped[str] = mapped_column(String(20), default="new")
    audio_filename: Mapped[str | None] = mapped_column(String(300))
    audio_path: Mapped[str | None] = mapped_column(String(500))
    # "recorded" (in-app, stereo coach/client channels) or "uploaded"
    audio_source: Mapped[str | None] = mapped_column(String(20))
    transcript_path: Mapped[str | None] = mapped_column(String(500))
    duration_seconds: Mapped[float | None]
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    client: Mapped[Client] = relationship(back_populates="sessions")
    documents: Mapped[list["Document"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="Document.id"
    )


class Document(Base):
    """A generated coaching document, stored as Tiptap JSON so Maria's edits
    round-trip losslessly through the editor. One row per (session, type);
    regeneration overwrites it."""

    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("session_id", "doc_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    doc_type: Mapped[str] = mapped_column(String(20))  # summary | homework | next_session
    title: Mapped[str] = mapped_column(String(200), default="")
    content: Mapped[str] = mapped_column(Text)  # Tiptap document JSON
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    session: Mapped[Session] = relationship(back_populates="documents")


Client.session_count = column_property(
    select(func.count(Session.id))
    .where(Session.client_id == Client.id)
    .correlate_except(Session)
    .scalar_subquery()
)
