"""Transcription engines behind a common interface.

MVP ships Deepgram Nova-3 batch (diarization built in). A local engine
(WhisperX + pyannote, see interview_recorder) can implement the same
Protocol later and be selected via config.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from app.config import settings


@dataclass
class TranscriptResult:
    markdown: str
    duration_seconds: float | None
    speaker_count: int


class Transcriber(Protocol):
    def transcribe(self, audio_path: Path) -> TranscriptResult: ...


def _format_timestamp(seconds: float, total: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if total >= 3600:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _merge_utterances(utterances) -> list[dict]:
    """Collapse consecutive same-speaker utterances into speaker turns."""
    turns: list[dict] = []
    for u in utterances:
        text = (u.transcript or "").strip()
        if not text:
            continue
        speaker = int(u.speaker) if u.speaker is not None else 0
        if turns and turns[-1]["speaker"] == speaker:
            turns[-1]["text"] += " " + text
            turns[-1]["end"] = u.end
        else:
            turns.append(
                {"speaker": speaker, "start": u.start, "end": u.end, "text": text}
            )
    return turns


def format_transcript_markdown(
    turns: list[dict], duration: float | None, engine: str
) -> str:
    """Render speaker turns as markdown (format borrowed from interview_recorder)."""
    # Relabel raw speaker ids as "Speaker 1/2…" by first appearance
    labels: dict[int, str] = {}
    for t in turns:
        if t["speaker"] not in labels:
            labels[t["speaker"]] = f"Speaker {len(labels) + 1}"

    total = duration or (turns[-1]["end"] if turns else 0)
    header = (
        f"**Duration:** {_format_timestamp(total, total)}\n"
        f"**Speakers detected:** {len(labels)}\n"
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"**Engine:** {engine}\n\n---\n\n"
    )
    body = [
        f"### {labels[t['speaker']]} · "
        f"[{_format_timestamp(t['start'], total)} – {_format_timestamp(t['end'], total)}]\n"
        f"{t['text']}\n"
        for t in turns
    ]
    return header + "\n".join(body) + "\n"


class DeepgramTranscriber:
    """Deepgram Nova-3 batch transcription with built-in diarization."""

    def __init__(self) -> None:
        if not settings.deepgram_api_key:
            raise RuntimeError(
                "DEEPGRAM_API_KEY is not configured — add it to the repo-root .env"
            )

    def transcribe(self, audio_path: Path) -> TranscriptResult:
        from deepgram import DeepgramClient

        client = DeepgramClient(api_key=settings.deepgram_api_key, timeout=600.0)

        response = client.listen.v1.media.transcribe_file(
            request=audio_path.read_bytes(),
            model=settings.deepgram_model,
            language=settings.transcription_language,
            smart_format=True,
            punctuate=True,
            diarize=True,
            utterances=True,
        )

        duration = getattr(getattr(response, "metadata", None), "duration", None)
        utterances = getattr(getattr(response, "results", None), "utterances", None)
        if not utterances:
            raise RuntimeError("Deepgram returned no utterances for this audio")

        turns = _merge_utterances(utterances)
        markdown = format_transcript_markdown(
            turns, duration, f"deepgram {settings.deepgram_model}"
        )
        return TranscriptResult(
            markdown=markdown,
            duration_seconds=duration,
            speaker_count=len({t["speaker"] for t in turns}),
        )


def get_transcriber() -> Transcriber:
    return DeepgramTranscriber()
