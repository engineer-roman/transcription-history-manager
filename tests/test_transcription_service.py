"""Tests for transcription service."""

from datetime import datetime
from pathlib import Path

import pytest

from app.models.transcription import TranscriptionMetadata
from app.repositories.base import TranscriptionRepository
from app.services.transcription_service import TranscriptionService


class MockRepository(TranscriptionRepository):
    """Mock repository for testing."""

    def __init__(self, base_directory: Path) -> None:
        super().__init__(base_directory)
        self.transcriptions = [
            TranscriptionMetadata(
                timestamp=1234567890,
                directory=Path("/fake/1234567890"),
                audio_file=Path("/fake/1234567890/audio.wav"),
                transcription_text="Hello world, this is a test transcription.",
                created_at=datetime(2023, 1, 1, 12, 0, 0),
            ),
            TranscriptionMetadata(
                timestamp=1234567891,
                directory=Path("/fake/1234567891"),
                audio_file=Path("/fake/1234567891/audio.wav"),
                transcription_text="Another test transcription here.",
                created_at=datetime(2023, 1, 2, 12, 0, 0),
            ),
        ]

    async def get_all_transcriptions(self) -> list[TranscriptionMetadata]:
        return self.transcriptions

    async def get_transcription_by_timestamp(
        self, timestamp: int
    ) -> TranscriptionMetadata | None:
        for trans in self.transcriptions:
            if trans.timestamp == timestamp:
                return trans
        return None

    async def read_audio_file(self, transcription: TranscriptionMetadata) -> bytes:
        return b"fake audio data"


@pytest.mark.asyncio
async def test_get_all_conversations() -> None:
    """Test getting all conversations."""
    repository = MockRepository(Path("/fake"))
    service = TranscriptionService(repository)

    conversations = await service.get_all_conversations()

    assert len(conversations) == 2
    assert all(conv.conversation_id for conv in conversations)
    assert all(conv.title for conv in conversations)


@pytest.mark.asyncio
async def test_get_conversation_by_id() -> None:
    """Test getting a specific conversation."""
    repository = MockRepository(Path("/fake"))
    service = TranscriptionService(repository)

    conversations = await service.get_all_conversations()
    first_conv_id = conversations[0].conversation_id

    conversation = await service.get_conversation_by_id(first_conv_id)

    assert conversation is not None
    assert conversation.conversation_id == first_conv_id


@pytest.mark.asyncio
async def test_search_conversations() -> None:
    """Test searching conversations."""
    repository = MockRepository(Path("/fake"))
    service = TranscriptionService(repository)

    results = await service.search_conversations("test")

    assert len(results) > 0
    for conv, matches in results:
        assert len(matches) > 0


@pytest.mark.asyncio
async def test_search_conversations_no_results() -> None:
    """Test searching with no matching results."""
    repository = MockRepository(Path("/fake"))
    service = TranscriptionService(repository)

    results = await service.search_conversations("nonexistent query xyz")

    assert len(results) == 0


@pytest.mark.asyncio
async def test_get_audio_file() -> None:
    """Test getting audio file."""
    repository = MockRepository(Path("/fake"))
    service = TranscriptionService(repository)

    conversations = await service.get_all_conversations()
    first_conv = conversations[0]
    first_version = first_conv.versions[0]

    audio_data = await service.get_audio_file(
        first_conv.conversation_id, first_version.version_id
    )

    assert audio_data == b"fake audio data"
