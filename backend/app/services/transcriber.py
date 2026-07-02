"""Transcription engines behind a common interface.

MVP ships Deepgram Nova-3 batch. Two modes:

- Uploaded audio: diarization (voice-based speaker guessing, "Speaker 1/2").
- In-app recordings: multichannel — the stereo file is physically split
  (left = coach mic, right = client via BlackHole), so each channel is
  transcribed separately and labeled by name. No guessing.

A local engine (WhisperX + pyannote, see interview_recorder) can implement
the same Protocol later and be selected via config.
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
    def transcribe(
        self, audio_path: Path, channel_labels: tuple[str, str] | None = None
    ) -> TranscriptResult: ...


def _format_timestamp(seconds: float, total: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if total >= 3600:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _merge_utterances(utterances, by_channel: bool = False) -> list[dict]:
    """Collapse consecutive same-speaker utterances into speaker turns.

    Speaker identity comes from diarization (u.speaker) or, for stereo
    recordings, from the physical channel (u.channel).
    """
    ordered = sorted(utterances, key=lambda u: u.start or 0)
    turns: list[dict] = []
    for u in ordered:
        text = (u.transcript or "").strip()
        if not text:
            continue
        raw = u.channel if by_channel else u.speaker
        speaker = int(raw) if raw is not None else 0
        if turns and turns[-1]["speaker"] == speaker:
            turns[-1]["text"] += " " + text
            turns[-1]["end"] = u.end
        else:
            turns.append(
                {"speaker": speaker, "start": u.start, "end": u.end, "text": text}
            )
    return turns


def format_transcript_markdown(
    turns: list[dict],
    duration: float | None,
    engine: str,
    labels: dict[int, str] | None = None,
) -> str:
    """Render speaker turns as markdown (format borrowed from interview_recorder)."""
    if labels is None:
        # Relabel raw speaker ids as "Speaker 1/2…" by first appearance
        labels = {}
        for t in turns:
            if t["speaker"] not in labels:
                labels[t["speaker"]] = f"Speaker {len(labels) + 1}"

    total = duration or (turns[-1]["end"] if turns else 0)
    speakers_used = {t["speaker"] for t in turns}
    header = (
        f"**Duration:** {_format_timestamp(total, total)}\n"
        f"**Speakers detected:** {len(speakers_used)}\n"
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"**Engine:** {engine}\n\n---\n\n"
    )
    def label(speaker_id: int) -> str:
        return labels.get(speaker_id, f"Speaker {speaker_id + 1}")

    body = [
        f"### {label(t['speaker'])} · "
        f"[{_format_timestamp(t['start'], total)} – {_format_timestamp(t['end'], total)}]\n"
        f"{t['text']}\n"
        for t in turns
    ]
    return header + "\n".join(body) + "\n"


class DeepgramTranscriber:
    """Deepgram Nova-3 batch transcription (diarize or multichannel)."""

    def __init__(self) -> None:
        if not settings.deepgram_api_key:
            raise RuntimeError(
                "DEEPGRAM_API_KEY is not configured — add it to the repo-root .env"
            )

    def transcribe(
        self, audio_path: Path, channel_labels: tuple[str, str] | None = None
    ) -> TranscriptResult:
        from deepgram import DeepgramClient

        client = DeepgramClient(api_key=settings.deepgram_api_key, timeout=600.0)
        multichannel = channel_labels is not None

        response = client.listen.v1.media.transcribe_file(
            request=audio_path.read_bytes(),
            model=settings.deepgram_model,
            language=settings.transcription_language,
            smart_format=True,
            punctuate=True,
            diarize=not multichannel,
            multichannel=multichannel,
            utterances=True,
        )

        duration = getattr(getattr(response, "metadata", None), "duration", None)
        utterances = getattr(getattr(response, "results", None), "utterances", None)
        if not utterances:
            raise RuntimeError("Deepgram returned no utterances for this audio")

        turns = _merge_utterances(utterances, by_channel=multichannel)
        engine = f"deepgram {settings.deepgram_model}"
        labels: dict[int, str] | None = None
        if channel_labels is not None:
            labels = {0: channel_labels[0], 1: channel_labels[1]}
            engine += " (multichannel)"
        markdown = format_transcript_markdown(turns, duration, engine, labels)
        return TranscriptResult(
            markdown=markdown,
            duration_seconds=duration,
            speaker_count=len({t["speaker"] for t in turns}),
        )


def get_transcriber() -> Transcriber:
    return DeepgramTranscriber()
