"""API endpoints for conversations."""

import math
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response

from app.api.dependencies import get_transcription_service
from app.schemas.transcription import (
    ConversationListItemSchema,
    ConversationSchema,
    PaginatedConversationListResponse,
    PaginatedSearchResultResponse,
    PaginationMetadata,
    SearchResultSchema,
)
from app.services.transcription_service import TranscriptionService

router = APIRouter()


@router.get("/conversations", response_model=PaginatedConversationListResponse)
async def list_conversations(
    service: Annotated[TranscriptionService, Depends(get_transcription_service)],
    page: Annotated[int, Query(ge=1, description="Page number (1-indexed)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 30,
) -> PaginatedConversationListResponse:
    """
    Get paginated list of conversations.

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page (max 100)

    Returns:
        Paginated list of conversation summaries
    """
    # Get paginated results from the search index
    results, total = await service.get_paginated_conversations(page=page, page_size=page_size)

    # Convert to schema
    items = []
    for row in results:
        items.append(
            ConversationListItemSchema(
                conversation_id=row["conversation_id"],
                title=row["title"],
                latest_timestamp=row["timestamp"],
                version_count=1,  # We only store latest in index, need to count if needed
                created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
                updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None,
            )
        )

    # Calculate pagination metadata
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    pagination = PaginationMetadata(
        page=page,
        page_size=page_size,
        total_items=total,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )

    return PaginatedConversationListResponse(items=items, pagination=pagination)


@router.get("/conversations/{conversation_id}", response_model=ConversationSchema)
async def get_conversation(
    conversation_id: str,
    service: Annotated[TranscriptionService, Depends(get_transcription_service)],
) -> ConversationSchema:
    """
    Get detailed information about a specific conversation.

    Args:
        conversation_id: Conversation identifier

    Returns:
        Conversation details with all versions
    """
    conversation = await service.get_conversation_by_id(conversation_id)

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Convert to schema
    from app.schemas.transcription import AudioVersionSchema, TranscriptionMetadataSchema

    versions = [
        AudioVersionSchema(
            version_id=v.version_id,
            timestamp=v.timestamp,
            transcription=TranscriptionMetadataSchema(
                timestamp=v.transcription.timestamp,
                directory=str(v.transcription.directory),
                audio_file=str(v.transcription.audio_file)
                if v.transcription.audio_file
                else None,
                raw_transcription=v.transcription.transcription_text,
                transcription_with_timecodes=[
                    {
                        "start_time": tc.get("start_time", 0),
                        "end_time": tc.get("end_time", 0),
                        "text": tc.get("text", ""),
                    }
                    for tc in (v.transcription.transcription_with_timecodes or [])
                ],
                llm_output=v.transcription.llm_output,
                duration=v.transcription.duration,
                created_at=v.transcription.created_at,
            ),
            is_latest=v.is_latest,
        )
        for v in conversation.versions
    ]

    latest_version = None
    if conversation.latest_version:
        v = conversation.latest_version
        latest_version = AudioVersionSchema(
            version_id=v.version_id,
            timestamp=v.timestamp,
            transcription=TranscriptionMetadataSchema(
                timestamp=v.transcription.timestamp,
                directory=str(v.transcription.directory),
                audio_file=str(v.transcription.audio_file)
                if v.transcription.audio_file
                else None,
                raw_transcription=v.transcription.transcription_text,
                transcription_with_timecodes=[
                    {
                        "start_time": tc.get("start_time", 0),
                        "end_time": tc.get("end_time", 0),
                        "text": tc.get("text", ""),
                    }
                    for tc in (v.transcription.transcription_with_timecodes or [])
                ],
                llm_output=v.transcription.llm_output,
                duration=v.transcription.duration,
                created_at=v.transcription.created_at,
            ),
            is_latest=v.is_latest,
        )

    return ConversationSchema(
        conversation_id=conversation.conversation_id,
        title=conversation.title,
        versions=versions,
        latest_version=latest_version,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


@router.get("/conversations/search", response_model=PaginatedSearchResultResponse)
async def search_conversations(
    q: Annotated[str, Query(min_length=1, description="Search query")],
    service: Annotated[TranscriptionService, Depends(get_transcription_service)],
    page: Annotated[int, Query(ge=1, description="Page number (1-indexed)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 30,
) -> PaginatedSearchResultResponse:
    """
    Search for conversations matching a query with pagination.

    Uses SQLite FTS5 for fast full-text search with highlighting.

    Args:
        q: Search query string
        page: Page number (1-indexed)
        page_size: Number of items per page (max 100)

    Returns:
        Paginated search results with matching snippets
    """
    # Use the new FTS5-based search with pagination
    results, total = await service.search_conversations_paginated(
        query=q, page=page, page_size=page_size
    )

    # Convert to schema
    items = []
    for row in results:
        items.append(
            SearchResultSchema(
                conversation_id=row["conversation_id"],
                title=row["title"],
                matches=row.get("match_snippets", []),
                latest_timestamp=row["timestamp"],
                version_count=1,  # We only store latest in index
            )
        )

    # Calculate pagination metadata
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    pagination = PaginationMetadata(
        page=page,
        page_size=page_size,
        total_items=total,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )

    return PaginatedSearchResultResponse(items=items, pagination=pagination)


@router.get("/conversations/{conversation_id}/audio/{version_id}")
async def get_audio_file(
    conversation_id: str,
    version_id: str,
    service: Annotated[TranscriptionService, Depends(get_transcription_service)],
) -> FileResponse:
    """
    Get audio file for a specific conversation version.

    Args:
        conversation_id: Conversation identifier
        version_id: Version identifier (timestamp)

    Returns:
        Audio file (WAV format) with range request support for seeking
    """
    try:
        audio_file_path = await service.get_audio_file_path(conversation_id, version_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return FileResponse(
        path=audio_file_path,
        media_type="audio/wav",
        filename=f"audio_{version_id}.wav",
    )
