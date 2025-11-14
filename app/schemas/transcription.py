"""Pydantic schemas for transcription API."""

from datetime import datetime

from pydantic import BaseModel, Field


class TimecodeEntry(BaseModel):
    """Single timecode entry with text."""

    start_time: float = Field(..., description="Start time in seconds")
    end_time: float = Field(..., description="End time in seconds")
    text: str = Field(..., description="Transcribed text for this time range")


class TranscriptionMetadataSchema(BaseModel):
    """Schema for transcription metadata."""

    timestamp: int
    directory: str
    audio_file: str | None = None
    raw_transcription: str | None = None
    transcription_with_timecodes: list[TimecodeEntry] | None = None
    llm_output: str | None = None
    duration: float | None = None
    created_at: datetime | None = None


class AudioVersionSchema(BaseModel):
    """Schema for audio version/attempt."""

    version_id: str
    timestamp: int
    transcription: TranscriptionMetadataSchema
    is_latest: bool = False


class ConversationSchema(BaseModel):
    """Schema for conversation."""

    conversation_id: str
    title: str
    versions: list[AudioVersionSchema]
    latest_version: AudioVersionSchema | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ConversationListItemSchema(BaseModel):
    """Schema for conversation list item (summary)."""

    conversation_id: str
    title: str
    latest_timestamp: int
    version_count: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SearchResultSchema(BaseModel):
    """Schema for search results."""

    conversation_id: str
    title: str
    matches: list[str] = Field(
        ..., description="Text snippets matching the search query"
    )
    latest_timestamp: int
    version_count: int
