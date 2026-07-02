"""Session read/update/delete + audio upload, transcription, SSE progress."""

import asyncio
import json
import shutil

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy.orm import Session as DbSession

from app import models, schemas
from app.config import settings
from app.db import SessionLocal, get_db
from app.services import progress
from app.services.transcription_job import run_transcription

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

AUDIO_EXTENSIONS = {".m4a", ".mp3", ".wav", ".mp4", ".aac", ".flac", ".ogg", ".webm"}


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
    session_dir = settings.data_dir / "sessions" / str(session_id)
    if session_dir.is_dir():
        shutil.rmtree(session_dir)
    db.delete(session)
    db.commit()


# --- Audio & transcription ---


@router.post("/{session_id}/audio", response_model=schemas.SessionRead)
def upload_audio(
    session_id: int,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: DbSession = Depends(get_db),
):
    session = _get_session_or_404(session_id, db)
    if session.status in ("transcribing", "recording"):
        raise HTTPException(status_code=409, detail=f"Session is busy ({session.status})")

    suffix = ("." + file.filename.rsplit(".", 1)[-1].lower()) if file.filename and "." in file.filename else ""
    if suffix not in AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported audio format '{suffix}'. Accepted: {', '.join(sorted(AUDIO_EXTENSIONS))}",
        )

    session_dir = settings.data_dir / "sessions" / str(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    for old in session_dir.glob("audio.*"):
        old.unlink()

    audio_rel = f"sessions/{session_id}/audio{suffix}"
    with (settings.data_dir / audio_rel).open("wb") as out:
        shutil.copyfileobj(file.file, out)

    session.audio_filename = file.filename
    session.audio_path = audio_rel
    session.audio_source = "uploaded"
    session.transcript_path = None
    session.duration_seconds = None
    session.error_message = None
    session.status = "transcribing"
    db.commit()
    db.refresh(session)

    progress.set_stage(session_id, "uploaded", "Audio saved")
    background_tasks.add_task(run_transcription, session_id)
    return session


@router.post("/{session_id}/transcribe", response_model=schemas.SessionRead)
def retry_transcription(
    session_id: int,
    background_tasks: BackgroundTasks,
    db: DbSession = Depends(get_db),
):
    session = _get_session_or_404(session_id, db)
    if session.status in ("transcribing", "recording"):
        raise HTTPException(status_code=409, detail=f"Session is busy ({session.status})")
    if not session.audio_path:
        raise HTTPException(status_code=422, detail="No audio uploaded for this session")

    session.status = "transcribing"
    session.error_message = None
    db.commit()
    db.refresh(session)

    progress.set_stage(session_id, "uploaded", "Restarting transcription")
    background_tasks.add_task(run_transcription, session_id)
    return session


@router.get("/{session_id}/transcript", response_class=PlainTextResponse)
def get_transcript(session_id: int, db: DbSession = Depends(get_db)):
    session = _get_session_or_404(session_id, db)
    if not session.transcript_path:
        raise HTTPException(status_code=404, detail="No transcript for this session")
    path = settings.data_dir / session.transcript_path
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Transcript file missing on disk")
    return path.read_text(encoding="utf-8")


def _db_stage(session_id: int) -> dict:
    """Fallback when no job is active: derive a terminal stage from DB status."""
    db = SessionLocal()
    try:
        session = db.get(models.Session, session_id)
        if session is None:
            return {"stage": "error", "detail": "Session not found"}
        if session.status == "transcribed":
            return {"stage": "done", "detail": ""}
        if session.status == "error":
            return {"stage": "error", "detail": session.error_message or ""}
        return {"stage": session.status, "detail": ""}
    finally:
        db.close()


@router.get("/{session_id}/events")
async def transcription_events(session_id: int):
    """SSE stream of transcription progress; closes on done/error."""

    async def stream():
        last = None
        while True:
            state = progress.get_stage(session_id) or _db_stage(session_id)
            if state != last:
                yield f"data: {json.dumps(state)}\n\n"
                last = state
            if state["stage"] in progress.TERMINAL_STAGES or state["stage"] == "new":
                progress.clear(session_id)
                break
            await asyncio.sleep(0.4)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
