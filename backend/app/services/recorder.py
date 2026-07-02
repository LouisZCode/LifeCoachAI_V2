"""In-app call recording: mic (left channel) + BlackHole system audio (right).

Ported from the proven interview_recorder pipeline. Speaker identity is
physical — the left channel is whatever the mic hears (the coach), the right
channel is whatever the Mac plays (the client on Zoom/Meet/phone) — so the
transcript needs no diarization guessing.

Mac prerequisites (one-time): the BlackHole 2ch driver, plus a Multi-Output
Device combining headphones + BlackHole (named "Recording Output") selected
as system output while on the call. `preflight()` reports all of this so the
UI can guide the coach instead of failing silently.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from pathlib import Path
from typing import Callable

import numpy as np
import sounddevice as sd
import soundfile as sf

from app.config import settings
from app.services import macos_audio

BLOCKSIZE = 1024


class RecorderError(RuntimeError):
    """User-facing recording problem (missing device, already active, ...)."""


# --- Device discovery ---


def _is_blackhole(name: str) -> bool:
    return settings.blackhole_device_name.lower() in name.lower()


def find_blackhole() -> tuple[int, str] | None:
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0 and _is_blackhole(d["name"]):
            return i, d["name"]
    return None


def find_mic() -> tuple[int, str] | None:
    """Default input device — unless that IS BlackHole (a common leftover when
    the default input got switched), in which case fall back to the first real
    microphone so both channels don't end up recording the call audio."""
    try:
        idx = sd.default.device[0]
        if idx is not None and idx >= 0:
            name = sd.query_devices(idx)["name"]
            if not _is_blackhole(name):
                return int(idx), name
    except Exception:
        pass
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0 and not _is_blackhole(d["name"]):
            return i, d["name"]
    return None


def default_output_name() -> str | None:
    # CoreAudio gives the *current* default output; the PortAudio fallback is
    # a snapshot from process start and goes stale when devices change.
    live = macos_audio.default_output_name()
    if live is not None:
        return live
    try:
        idx = sd.default.device[1]
        if idx is None or idx < 0:
            return None
        return str(sd.query_devices(idx)["name"])
    except Exception:
        return None


def output_check() -> dict:
    name = default_output_name()
    return {
        "name": name,
        "ok": name is not None
        and settings.recording_output_name.lower() in name.lower(),
    }


def preflight() -> dict:
    mic = find_mic()
    blackhole = find_blackhole()
    return {
        "mic": {"found": mic is not None, "name": mic[1] if mic else None},
        "blackhole": {
            "found": blackhole is not None,
            "name": blackhole[1] if blackhole else None,
        },
        "output": output_check(),
        "ready": mic is not None and blackhole is not None,
    }


# --- Capture ---


class DualStreamRecorder:
    """Two parallel input streams: mic -> left, BlackHole (mono mix) -> right."""

    def __init__(self, mic_index: int, bh_index: int):
        self.mic_index = mic_index
        self.bh_index = bh_index
        self._mic_chunks: deque[np.ndarray] = deque()
        self._bh_chunks: deque[np.ndarray] = deque()
        self._lock = threading.Lock()
        self._mic_stream: sd.InputStream | None = None
        self._bh_stream: sd.InputStream | None = None
        self._stopped = False
        self._mic_rms = 0.0
        self._bh_rms = 0.0

    def _mic_callback(self, indata, frames, time_info, status):
        block = indata.copy().reshape(-1)
        rms = float(np.sqrt(np.mean(block**2))) if block.size else 0.0
        with self._lock:
            self._mic_chunks.append(block)
            self._mic_rms = rms

    def _bh_callback(self, indata, frames, time_info, status):
        mono = (
            indata.mean(axis=1)
            if indata.ndim == 2 and indata.shape[1] > 1
            else indata.reshape(-1)
        )
        mono = mono.copy()
        rms = float(np.sqrt(np.mean(mono**2))) if mono.size else 0.0
        with self._lock:
            self._bh_chunks.append(mono)
            self._bh_rms = rms

    def levels(self) -> tuple[float, float]:
        with self._lock:
            return self._mic_rms, self._bh_rms

    def start(self) -> None:
        self._mic_stream = sd.InputStream(
            device=self.mic_index,
            channels=1,
            samplerate=settings.recording_sample_rate,
            blocksize=BLOCKSIZE,
            dtype="float32",
            callback=self._mic_callback,
        )
        self._mic_stream.start()
        self._bh_stream = sd.InputStream(
            device=self.bh_index,
            channels=2,
            samplerate=settings.recording_sample_rate,
            blocksize=BLOCKSIZE,
            dtype="float32",
            callback=self._bh_callback,
        )
        self._bh_stream.start()

    def stop_and_get_stereo(self) -> np.ndarray:
        if self._stopped:
            return np.zeros((0, 2), dtype=np.float32)
        self._stopped = True
        for s in (self._mic_stream, self._bh_stream):
            if s is not None:
                try:
                    s.stop()
                    s.close()
                except Exception:
                    pass

        with self._lock:
            mic = (
                np.concatenate(list(self._mic_chunks))
                if self._mic_chunks
                else np.zeros(0, dtype=np.float32)
            )
            bh = (
                np.concatenate(list(self._bh_chunks))
                if self._bh_chunks
                else np.zeros(0, dtype=np.float32)
            )

        n = max(mic.size, bh.size)
        if n == 0:
            return np.zeros((0, 2), dtype=np.float32)
        if mic.size < n:
            mic = np.pad(mic, (0, n - mic.size))
        if bh.size < n:
            bh = np.pad(bh, (0, n - bh.size))
        return np.stack([mic.astype(np.float32), bh.astype(np.float32)], axis=1)


# --- Single-active-recording manager (single-user local app) ---


class RecordingManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._recorder: DualStreamRecorder | None = None
        self._session_id: int | None = None
        self._started_monotonic: float | None = None
        self._ceiling_timer: threading.Timer | None = None

    @property
    def active_session_id(self) -> int | None:
        with self._lock:
            return self._session_id

    def status(self) -> dict:
        with self._lock:
            if self._recorder is None:
                return {"active": False}
            mic_rms, bh_rms = self._recorder.levels()
            return {
                "active": True,
                "session_id": self._session_id,
                "elapsed_seconds": time.monotonic() - (self._started_monotonic or 0.0),
                "mic_level": mic_rms,
                "system_level": bh_rms,
                "output": output_check(),
            }

    def start(self, session_id: int, on_ceiling: Callable[[int], None]) -> None:
        with self._lock:
            if self._recorder is not None:
                raise RecorderError(
                    f"A recording is already running for session {self._session_id}"
                )
            mic = find_mic()
            blackhole = find_blackhole()
            if mic is None:
                raise RecorderError(
                    "No microphone found. Pick one in System Settings → Sound → Input."
                )
            if blackhole is None:
                raise RecorderError(
                    "BlackHole 2ch not found — install it with 'brew install "
                    "blackhole-2ch', then create the 'Recording Output' "
                    "Multi-Output Device in Audio MIDI Setup."
                )
            recorder = DualStreamRecorder(mic_index=mic[0], bh_index=blackhole[0])
            try:
                recorder.start()
            except Exception as e:
                recorder.stop_and_get_stereo()
                raise RecorderError(f"Could not open audio streams: {e}") from e

            self._recorder = recorder
            self._session_id = session_id
            self._started_monotonic = time.monotonic()
            self._ceiling_timer = threading.Timer(
                settings.recording_max_minutes * 60.0, on_ceiling, args=[session_id]
            )
            self._ceiling_timer.daemon = True
            self._ceiling_timer.start()

    def stop(self, save_to: Path) -> float:
        """Stop, write the stereo WAV, return its duration in seconds."""
        with self._lock:
            recorder = self._take_active()
        stereo = recorder.stop_and_get_stereo()
        if stereo.shape[0] == 0:
            raise RecorderError("No audio was captured.")
        save_to.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(save_to), stereo, settings.recording_sample_rate, subtype="PCM_16")
        return stereo.shape[0] / settings.recording_sample_rate

    def cancel(self) -> None:
        with self._lock:
            if self._recorder is None:
                return
            recorder = self._take_active()
        recorder.stop_and_get_stereo()

    def _take_active(self) -> DualStreamRecorder:
        """Detach the active recorder (caller holds the lock)."""
        if self._recorder is None:
            raise RecorderError("No recording is running.")
        recorder = self._recorder
        self._recorder = None
        self._session_id = None
        self._started_monotonic = None
        if self._ceiling_timer is not None:
            self._ceiling_timer.cancel()
            self._ceiling_timer = None
        return recorder


manager = RecordingManager()
