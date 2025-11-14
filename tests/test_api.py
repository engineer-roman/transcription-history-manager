"""Tests for API endpoints."""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.transcription import AudioVersion, Conversation, TranscriptionMetadata

client = TestClient(app)


@pytest.fixture
def mock_service() -> AsyncMock:
    """Create a mock transcription service."""
    service = AsyncMock()

    # Mock conversation data
    trans = TranscriptionMetadata(
        timestamp=1234567890,
        directory=Path("/fake/1234567890"),
        audio_file=Path("/fake/1234567890/audio.wav"),
        transcription_text="Test transcription",
        created_at=datetime(2023, 1, 1, 12, 0, 0),
    )

    version = AudioVersion(
        version_id="1234567890",
        timestamp=1234567890,
        transcription=trans,
        is_latest=True,
    )

    conversation = Conversation(
        conversation_id="test-conv-1",
        title="Test Conversation",
        versions=[version],
        latest_version=version,
        created_at=datetime(2023, 1, 1, 12, 0, 0),
        updated_at=datetime(2023, 1, 1, 12, 0, 0),
    )

    service.get_all_conversations.return_value = [conversation]
    service.get_conversation_by_id.return_value = conversation
    service.search_conversations.return_value = [(conversation, ["Test match"])]
    service.get_audio_file.return_value = b"fake audio data"

    return service


def test_list_conversations(mock_service: AsyncMock) -> None:
    """Test listing all conversations."""
    with patch("app.api.routes.conversations.get_transcription_service", return_value=mock_service):
        response = client.get("/api/v1/conversations")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["conversation_id"] == "test-conv-1"
        assert data[0]["title"] == "Test Conversation"


def test_get_conversation_details(mock_service: AsyncMock) -> None:
    """Test getting conversation details."""
    with patch("app.api.routes.conversations.get_transcription_service", return_value=mock_service):
        response = client.get("/api/v1/conversations/test-conv-1")

        assert response.status_code == 200
        data = response.json()
        assert data["conversation_id"] == "test-conv-1"
        assert data["title"] == "Test Conversation"
        assert len(data["versions"]) == 1


def test_get_conversation_not_found(mock_service: AsyncMock) -> None:
    """Test getting non-existent conversation."""
    mock_service.get_conversation_by_id.return_value = None

    with patch("app.api.routes.conversations.get_transcription_service", return_value=mock_service):
        response = client.get("/api/v1/conversations/nonexistent")

        assert response.status_code == 404


def test_search_conversations(mock_service: AsyncMock) -> None:
    """Test searching conversations."""
    with patch("app.api.routes.conversations.get_transcription_service", return_value=mock_service):
        response = client.get("/api/v1/conversations/search?q=test")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["conversation_id"] == "test-conv-1"
        assert len(data[0]["matches"]) > 0


def test_search_conversations_no_query() -> None:
    """Test search without query parameter."""
    response = client.get("/api/v1/conversations/search")

    assert response.status_code == 422  # Validation error


def test_get_audio_file(mock_service: AsyncMock) -> None:
    """Test getting audio file."""
    with patch("app.api.routes.conversations.get_transcription_service", return_value=mock_service):
        response = client.get("/api/v1/conversations/test-conv-1/audio/1234567890")

        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"
        assert response.content == b"fake audio data"
