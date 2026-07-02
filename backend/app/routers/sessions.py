"""Session read/update/delete (creation is nested under clients)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DbSession

from app import models, schemas
from app.db import get_db

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _get_session_or_404(session_id: int, db: DbSession) -> models.Session:
    session = db.get(models.Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/{session_id}", response_model=schemas.SessionRead)
def get_session(session_id: int, db: DbSession = Depends(get_db)):
    return _get_session_or_404(session_id, db)


@router.patch("/{session_id}", response_model=schemas.SessionRead)
def update_session(
    session_id: int, payload: schemas.SessionUpdate, db: DbSession = Depends(get_db)
):
    session = _get_session_or_404(session_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(session, field, value)
    db.commit()
    db.refresh(session)
    return session


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: int, db: DbSession = Depends(get_db)):
    session = _get_session_or_404(session_id, db)
    db.delete(session)
    db.commit()
