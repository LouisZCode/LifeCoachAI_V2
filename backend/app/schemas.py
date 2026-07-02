"""Pydantic schemas for the clients/sessions/documents API."""

import json
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


# --- Sessions ---


class SessionCreate(BaseModel):
    session_date: date
    title: str = ""
    notes: str = ""


class SessionUpdate(BaseModel):
    session_date: date | None = None
    title: str | None = None
    notes: str | None = None


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    title: str
    session_date: date
    notes: str
    status: str
    audio_filename: str | None
    audio_source: str | None
    duration_seconds: float | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


# --- Documents ---


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    doc_type: str
    title: str
    content: dict  # Tiptap document JSON
    updated_at: datetime

    @field_validator("content", mode="before")
    @classmethod
    def _parse_content(cls, value):
        # Stored as a JSON string in SQLite; served as a real object.
        return json.loads(value) if isinstance(value, str) else value


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    content: dict | None = None


# --- Clients ---


class ClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str | None = None
    notes: str = ""


class ClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    email: str | None = None
    notes: str | None = None


class ClientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str | None
    notes: str
    session_count: int
    created_at: datetime
    updated_at: datetime


class ClientDetail(ClientRead):
    sessions: list[SessionRead]
