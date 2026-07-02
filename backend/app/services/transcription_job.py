"""Background transcription job: audio file -> transcript.md + session status.

Runs in a worker thread (FastAPI BackgroundTasks), so it opens its own DB
session and reports progress through the in-memory progress store.
"""

from app import models
from app.config import settings
from app.db import SessionLocal
from app.services import progress
from app.services.transcriber import get_transcriber


def run_transcription(session_id: int) -> None:
    db = SessionLocal()
    try:
        session = db.get(models.Session, session_id)
        if session is None or not session.audio_path:
            progress.set_stage(session_id, "error", "Session or audio file missing")
            return

        progress.set_stage(session_id, "transcribing", "Sending audio to Deepgram")
        transcriber = get_transcriber()
        result = transcriber.transcribe(settings.data_dir / session.audio_path)

        progress.set_stage(session_id, "storing", "Saving transcript")
        transcript_rel = f"sessions/{session_id}/transcript.md"
        transcript_abs = settings.data_dir / transcript_rel
        transcript_abs.parent.mkdir(parents=True, exist_ok=True)
        transcript_abs.write_text(result.markdown, encoding="utf-8")

        session.transcript_path = transcript_rel
        session.duration_seconds = result.duration_seconds
        session.status = "transcribed"
        session.error_message = None
        db.commit()
        progress.set_stage(session_id, "done")
    except Exception as exc:
        db.rollback()
        session = db.get(models.Session, session_id)
        if session is not None:
            session.status = "error"
            session.error_message = str(exc)
            db.commit()
        progress.set_stage(session_id, "error", str(exc))
    finally:
        db.close()
