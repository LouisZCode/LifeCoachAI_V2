"""In-app call recording endpoints.

One recording at a time (single-user local app). Stopping saves the stereo
WAV as the session's audio and rolls straight into the existing
transcription flow — same progress SSE, same retry semantics.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session as DbSession

from app import models, schemas
from app.config import settings
from app.db import SessionLocal, get_db
from app.services import progress, recorder
from app.services.transcription_job import run_transcription

router = APIRouter(prefix="/api", tags=["recording"])


@router.get("/recording/preflight")
def recording_preflight() -> dict:
    state = recorder.preflight()
    state["active_session_id"] = recorder.manager.active_session_id
    return state


@router.get("/recording/status")
def recording_status() -> dict:
    return recorder.manager.status()


def _get_session_or_404(session_id: int, db: DbSession) -> models.Session:
    session = db.get(models.Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _restored_status(session: models.Session) -> str:
    """Status a session falls back to when a recording doesn't happen —
    audio/transcript are only touched on successful finalize."""
    return "transcribed" if session.transcript_path else "new"


@router.post(
    "/sessions/{session_id}/recording/start", response_model=schemas.SessionRead
)
def start_recording(session_id: int, db: DbSession = Depends(get_db)):
    session = _get_session_or_404(session_id, db)
    if session.status in ("recording", "transcribing"):
        raise HTTPException(status_code=409, detail=f"Session is busy ({session.status})")

    try:
        recorder.manager.start(session_id, on_ceiling=_stop_at_ceiling)
    except recorder.RecorderError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    session.status = "recording"
    session.error_message = None
    db.commit()
    db.refresh(session)
    return session


@router.post(
    "/sessions/{session_id}/recording/stop", response_model=schemas.SessionRead
)
def stop_recording(
    session_id: int,
    background_tasks: BackgroundTasks,
    db: DbSession = Depends(get_db),
):
    session = _get_session_or_404(session_id, db)
    if recorder.manager.active_session_id != session_id:
        raise HTTPException(
            status_code=409, detail="No recording is running for this session"
        )

    try:
        finalized = _finalize_recording(session_id)
    except recorder.RecorderError as e:
        session.status = _restored_status(session)
        db.commit()
        raise HTTPException(status_code=422, detail=str(e)) from e

    background_tasks.add_task(run_transcription, session_id)
    return finalized


@router.post(
    "/sessions/{session_id}/recording/cancel", response_model=schemas.SessionRead
)
def cancel_recording(session_id: int, db: DbSession = Depends(get_db)):
    session = _get_session_or_404(session_id, db)
    if recorder.manager.active_session_id == session_id:
        recorder.manager.cancel()
    if session.status == "recording":
        session.status = _restored_status(session)
        db.commit()
        db.refresh(session)
    return session


def _finalize_recording(session_id: int) -> models.Session:
    """Stop the active recording, save the WAV, flip the session to
    transcribing. Uses its own DB session so the ceiling timer thread can
    call it too."""
    db = SessionLocal()
    try:
        session = db.get(models.Session, session_id)
        if session is None:
            recorder.manager.cancel()
            raise recorder.RecorderError("Session disappeared while recording")

        session_dir = settings.data_dir / "sessions" / str(session_id)
        audio_rel = f"sessions/{session_id}/audio.wav"
        for old in session_dir.glob("audio.*"):
            old.unlink()
        duration = recorder.manager.stop(settings.data_dir / audio_rel)

        session.audio_filename = "in-app-recording.wav"
        session.audio_path = audio_rel
        session.audio_source = "recorded"
        session.transcript_path = None
        session.duration_seconds = duration
        session.error_message = None
        session.status = "transcribing"
        db.commit()
        db.refresh(session)
        progress.set_stage(session_id, "uploaded", "Recording saved")
        return session
    finally:
        db.close()


def _stop_at_ceiling(session_id: int) -> None:
    """Hard-ceiling timer: save what we have instead of recording forever."""
    if recorder.manager.active_session_id != session_id:
        return
    try:
        _finalize_recording(session_id)
        run_transcription(session_id)
    except Exception as exc:
        db = SessionLocal()
        try:
            session = db.get(models.Session, session_id)
            if session is not None:
                session.status = "error"
                session.error_message = f"Recording auto-stop failed: {exc}"
                db.commit()
        finally:
            db.close()
        progress.set_stage(session_id, "error", str(exc))
