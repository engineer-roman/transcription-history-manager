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


class PaginationMetadata(BaseModel):
    """Pagination metadata for paginated responses."""

    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Number of items per page")
    total_items: int = Field(..., description="Total number of items")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")


class PaginatedConversationListResponse(BaseModel):
    """Paginated response for conversation list."""

    items: list[ConversationListItemSchema] = Field(..., description="List of conversations")
    pagination: PaginationMetadata = Field(..., description="Pagination metadata")


class PaginatedSearchResultResponse(BaseModel):
    """Paginated response for search results."""

    items: list[SearchResultSchema] = Field(..., description="List of search results")
    pagination: PaginationMetadata = Field(..., description="Pagination metadata")
