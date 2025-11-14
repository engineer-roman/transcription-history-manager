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

    # Transcription results at different processing stages
    raw_transcription: str | None = None  # rawResult - direct from STT
    preprocessed_transcription: str | None = None  # result - after preprocessing
    llm_transcription: str | None = None  # llmResult - after LLM processing

    # Legacy field for backward compatibility
    transcription_text: str | None = None

    # Timecode data
    segments: list[dict[str, str | float]] | None = None  # Detailed segments with timestamps
    transcription_with_timecodes: list[dict[str, str | float]] | None = None  # Legacy

    # Legacy LLM output field
    llm_output: str | None = None

    # Metadata from SuperWhisper
    duration: float | None = None  # Duration in milliseconds
    language: str | None = None  # Language code (e.g., "ru")
    model_name: str | None = None  # STT model name (e.g., "Ultra V3 Turbo")
    language_model_name: str | None = None  # LLM model name (e.g., "Claude 4.5 Haiku")
    mode_name: str | None = None  # Processing mode/preset name
    processing_time: int | None = None  # Total processing time in ms

    # Audio hash for version detection
    audio_hash: str | None = None  # SHA256 hash of audio file

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
