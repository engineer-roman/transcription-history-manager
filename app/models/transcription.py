"""Domain models for transcription data."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class TranscriptionMetadata:
    """Metadata for a transcription."""

    timestamp: int
    directory: Path
    audio_file: Path | None = None
    metadata_file: Path | None = None
    transcription_text: str | None = None
    transcription_with_timecodes: list[dict[str, str | float]] | None = None
    llm_output: str | None = None
    duration: float | None = None
    created_at: datetime | None = None


@dataclass
class AudioVersion:
    """Represents a version/attempt of transcription for the same audio."""

    version_id: str  # timestamp as string
    timestamp: int
    transcription: TranscriptionMetadata
    is_latest: bool = False


@dataclass
class Conversation:
    """Represents a conversation with potentially multiple transcription versions."""

    conversation_id: str  # hash or identifier grouping related recordings
    title: str
    versions: list[AudioVersion]
    latest_version: AudioVersion | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
