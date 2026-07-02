"""Application settings, loaded from environment / repo-root .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "LifeCoach AI"
    app_version: str = "0.1.0"

    # Vite dev server origin (only needed if the frontend bypasses the dev proxy)
    cors_origins: list[str] = ["http://localhost:5173"]

    # Langfuse observability — leave empty to run without tracing
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"


settings = Settings()
