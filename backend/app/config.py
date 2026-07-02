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

    # In-app call recording (mic = left channel, BlackHole = right channel).
    # Requires the BlackHole 2ch driver plus a Multi-Output Device named
    # "Recording Output" (headphones + BlackHole) selected as system output.
    coach_name: str = "Maria"
    blackhole_device_name: str = "BlackHole 2ch"
    recording_output_name: str = "Recording Output"
    recording_sample_rate: int = 16_000
    recording_max_minutes: float = 120.0

    # Document generation — OpenRouter (one key, any model), called via LangChain.
    # Models are per-stage: a cheap one reads the transcript (analysis), a strong
    # writing model produces the client-facing prose. Swap in .env, no code change.
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    analysis_model: str = "google/gemini-2.5-flash"
    writing_model: str = "anthropic/claude-sonnet-5"

    # Vite dev server origin (only needed if the frontend bypasses the dev proxy)
    cors_origins: list[str] = ["http://localhost:5173"]

    # Langfuse observability — leave empty to run without tracing
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"


settings = Settings()
