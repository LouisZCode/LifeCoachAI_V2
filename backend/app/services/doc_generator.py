"""Background document-generation job (P1 two-stage cascade).

    transcript ── analysis model ──► SessionAnalysis      (transcript sent ONCE)
    analysis ──── writing model ───► SessionSummary
    analysis ──── writing model ───► Homework
    analysis + summary ─ writing ──► NextSessionPrep

Runs in a worker thread (FastAPI BackgroundTasks): own DB session, progress
via the shared in-memory store/SSE. On failure the session falls back to
"transcribed" — the transcript is intact, generation can simply be retried.
"""

import json

from app import models
from app.agents import doc_schemas
from app.agents.llm import generate_structured
from app.agents.prompts import render_prompt
from app.config import settings
from app.db import SessionLocal
from app.services import doc_render, progress


def _upsert(db, session_id: int, doc_type: str, title: str, content: dict) -> None:
    document = (
        db.query(models.Document)
        .filter_by(session_id=session_id, doc_type=doc_type)
        .one_or_none()
    )
    if document is None:
        document = models.Document(session_id=session_id, doc_type=doc_type)
        db.add(document)
    document.title = title
    document.content = json.dumps(content, ensure_ascii=False)


def run_generation(session_id: int) -> None:
    db = SessionLocal()
    try:
        session = db.get(models.Session, session_id)
        if session is None or not session.transcript_path:
            progress.set_stage(session_id, "error", "Session or transcript missing")
            return

        transcript = (settings.data_dir / session.transcript_path).read_text(
            encoding="utf-8"
        )
        client_first_name = (
            session.client.name.split()[0] if session.client.name else "Client"
        )
        names = {"coach_name": settings.coach_name, "client_name": client_first_name}

        progress.set_stage(session_id, "analyzing", "Reading the transcript")
        analysis = generate_structured(
            render_prompt("analysis", transcript=transcript, **names),
            doc_schemas.SessionAnalysis,
            model=settings.analysis_model,
            trace_name=f"analysis:session-{session_id}",
        )
        analysis_text = analysis.model_dump_json(indent=1)
        language = analysis.session_language

        progress.set_stage(session_id, "writing_summary", "Writing the summary")
        summary = generate_structured(
            render_prompt("summary", analysis=analysis_text, language=language, **names),
            doc_schemas.SessionSummary,
            model=settings.writing_model,
            trace_name=f"summary:session-{session_id}",
        )

        progress.set_stage(session_id, "writing_homework", "Writing the homework")
        homework = generate_structured(
            render_prompt("homework", analysis=analysis_text, language=language, **names),
            doc_schemas.Homework,
            model=settings.writing_model,
            trace_name=f"homework:session-{session_id}",
        )

        progress.set_stage(session_id, "writing_next", "Preparing the next session")
        next_prep = generate_structured(
            render_prompt(
                "next_session",
                analysis=analysis_text,
                summary=summary.model_dump_json(indent=1),
                language=language,
                **names,
            ),
            doc_schemas.NextSessionPrep,
            model=settings.writing_model,
            trace_name=f"next_session:session-{session_id}",
        )

        progress.set_stage(session_id, "storing", "Saving documents")
        _upsert(db, session_id, "summary", summary.title, doc_render.render_summary(summary))
        _upsert(
            db,
            session_id,
            "homework",
            f"Homework: {homework.theme}",
            doc_render.render_homework(homework),
        )
        _upsert(
            db,
            session_id,
            "next_session",
            f"Next Session — {client_first_name}",
            doc_render.render_next_session(next_prep, client_first_name),
        )
        session.status = "docs_ready"
        session.error_message = None
        db.commit()
        progress.set_stage(session_id, "done")
    except Exception as exc:
        db.rollback()
        session = db.get(models.Session, session_id)
        if session is not None:
            session.status = "transcribed"  # transcript is fine — allow retry
            session.error_message = f"Document generation failed: {exc}"
            db.commit()
        progress.set_stage(session_id, "error", str(exc))
    finally:
        db.close()
