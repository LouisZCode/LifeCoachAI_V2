"""Application settings, loaded from environment / repo-root .env file."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor all paths to the repo root (backend/app/config.py -> ../../..)
# so the backend behaves the same no matter where it is launched from.
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    app_name: str = "LifeCoach AI"
    app_version: str = "0.1.0"

    # Local data area (SQLite db + per-session audio/transcript files)
    data_dir: Path = REPO_ROOT / "data"

    # Transcription — Deepgram Nova-3 batch with diarization
    deepgram_api_key: str = ""
    deepgram_model: str = "nova-3"
    # "multi" = code-switching across 10 languages incl. German/English;
    # set to "de"/"en" to pin a single language
    transcription_language: str = "multi"

    # Vite dev server origin (only needed if the frontend bypasses the dev proxy)
    cors_origins: list[str] = ["http://localhost:5173"]

    # Langfuse observability — leave empty to run without tracing
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"


settings = Settings()
