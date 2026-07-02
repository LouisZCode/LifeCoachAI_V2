"""Document generation + editing endpoints."""

import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session as DbSession

from app import models, schemas
from app.config import settings
from app.db import get_db
from app.services import progress
from app.services.doc_generator import run_generation

router = APIRouter(prefix="/api", tags=["documents"])

BUSY_STATUSES = {"recording", "transcribing", "generating"}


@router.post("/sessions/{session_id}/documents/generate", response_model=schemas.SessionRead)
def generate_documents(
    session_id: int,
    background_tasks: BackgroundTasks,
    db: DbSession = Depends(get_db),
):
    session = db.get(models.Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status in BUSY_STATUSES:
        raise HTTPException(status_code=409, detail=f"Session is busy ({session.status})")
    if not session.transcript_path:
        raise HTTPException(
            status_code=422, detail="Transcribe the session before generating documents"
        )
    # Fail here, visibly, instead of inside the background job.
    if not settings.openrouter_api_key:
        raise HTTPException(
            status_code=422,
            detail="OPENROUTER_API_KEY is missing in .env — add it and restart the app.",
        )

    session.status = "generating"
    session.error_message = None
    db.commit()
    db.refresh(session)

    progress.set_stage(session_id, "analyzing", "Starting")
    background_tasks.add_task(run_generation, session_id)
    return session


@router.get(
    "/sessions/{session_id}/documents", response_model=list[schemas.DocumentRead]
)
def list_documents(session_id: int, db: DbSession = Depends(get_db)):
    if db.get(models.Session, session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return (
        db.query(models.Document)
        .filter_by(session_id=session_id)
        .order_by(models.Document.id)
        .all()
    )


@router.patch("/documents/{document_id}", response_model=schemas.DocumentRead)
def update_document(
    document_id: int, payload: schemas.DocumentUpdate, db: DbSession = Depends(get_db)
):
    document = db.get(models.Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if payload.title is not None:
        document.title = payload.title
    if payload.content is not None:
        document.content = json.dumps(payload.content, ensure_ascii=False)
    db.commit()
    db.refresh(document)
    return document
