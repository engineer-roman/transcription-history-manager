"""API endpoints for conversations."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.api.dependencies import get_transcription_service
from app.schemas.transcription import (
    ConversationListItemSchema,
    ConversationSchema,
    SearchResultSchema,
)
from app.services.transcription_service import TranscriptionService

router = APIRouter()


@router.get("/conversations", response_model=list[ConversationListItemSchema])
async def list_conversations(
    service: Annotated[TranscriptionService, Depends(get_transcription_service)],
) -> list[ConversationListItemSchema]:
    """
    Get all conversations (list view).

    Returns:
        List of conversation summaries
    """
    conversations = await service.get_all_conversations()

    return [
        ConversationListItemSchema(
            conversation_id=conv.conversation_id,
            title=conv.title,
            latest_timestamp=conv.latest_version.timestamp if conv.latest_version else 0,
            version_count=len(conv.versions),
            created_at=conv.created_at,
            updated_at=conv.updated_at,
        )
        for conv in conversations
    ]


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


@router.get("/conversations/search", response_model=list[SearchResultSchema])
async def search_conversations(
    q: Annotated[str, Query(min_length=1, description="Search query")],
    service: Annotated[TranscriptionService, Depends(get_transcription_service)],
) -> list[SearchResultSchema]:
    """
    Search for conversations matching a query.

    Args:
        q: Search query string

    Returns:
        List of search results with matching snippets
    """
    results = await service.search_conversations(q)

    return [
        SearchResultSchema(
            conversation_id=conv.conversation_id,
            title=conv.title,
            matches=matches[:10],  # Limit to 10 matches per conversation
            latest_timestamp=conv.latest_version.timestamp if conv.latest_version else 0,
            version_count=len(conv.versions),
        )
        for conv, matches in results
    ]


@router.get("/conversations/{conversation_id}/audio/{version_id}")
async def get_audio_file(
    conversation_id: str,
    version_id: str,
    service: Annotated[TranscriptionService, Depends(get_transcription_service)],
) -> Response:
    """
    Get audio file for a specific conversation version.

    Args:
        conversation_id: Conversation identifier
        version_id: Version identifier (timestamp)

    Returns:
        Audio file (WAV format)
    """
    try:
        audio_data = await service.get_audio_file(conversation_id, version_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return Response(
        content=audio_data,
        media_type="audio/wav",
        headers={
            "Content-Disposition": f'inline; filename="audio_{version_id}.wav"',
        },
    )
