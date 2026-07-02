"""In-memory transcription progress, published to the UI via SSE.

The background worker (thread) writes stages here; the SSE endpoint polls
and streams changes. State is per-session and cleared on terminal stages.
"""

import threading

_lock = threading.Lock()
_state: dict[int, dict] = {}

TERMINAL_STAGES = {"done", "error"}


def set_stage(session_id: int, stage: str, detail: str = "") -> None:
    with _lock:
        _state[session_id] = {"stage": stage, "detail": detail}


def get_stage(session_id: int) -> dict | None:
    with _lock:
        return _state.get(session_id)


def clear(session_id: int) -> None:
    with _lock:
        _state.pop(session_id, None)
