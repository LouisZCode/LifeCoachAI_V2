"""Langfuse client wiring.

The app runs fine without Langfuse keys (client is None, tracing becomes a
no-op) — but the health endpoint reports it so a misconfiguration is visible
immediately instead of silently losing traces.
"""

from functools import lru_cache

from langfuse import Langfuse

from app.config import settings


@lru_cache(maxsize=1)
def get_langfuse() -> Langfuse | None:
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return None
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )


def langfuse_status() -> dict:
    client = get_langfuse()
    if client is None:
        return {"configured": False, "connected": False}
    try:
        connected = bool(client.auth_check())
    except Exception:
        connected = False
    return {"configured": True, "connected": connected}


def shutdown_langfuse() -> None:
    client = get_langfuse()
    if client is not None:
        client.flush()
