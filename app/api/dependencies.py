"""Dependency injection for API endpoints."""

from pathlib import Path

from app.core.config import settings
from app.repositories.superwhisper import SuperwhisperRepository
from app.services.transcription_service import TranscriptionService


def get_transcription_service() -> TranscriptionService:
    """
    Get transcription service instance.

    Returns:
        TranscriptionService instance
    """
    # Initialize repository with configured directory
    repository = SuperwhisperRepository(
        base_directory=Path(settings.superwhisper_directory)
    )

    # Initialize service
    service = TranscriptionService(repository=repository)

    return service
