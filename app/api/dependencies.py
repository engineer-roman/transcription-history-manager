"""Dependency injection for API endpoints."""

from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.repositories.superwhisper import SuperwhisperRepository
from app.services.indexing_service import IndexingService
from app.services.transcription_service import TranscriptionService

# Global indexing service instance
_indexing_service: Optional[IndexingService] = None


def set_indexing_service(service: IndexingService) -> None:
    """
    Set the global indexing service instance.

    This should be called once during application startup.

    Args:
        service: IndexingService instance to use globally
    """
    global _indexing_service
    _indexing_service = service


def get_indexing_service() -> Optional[IndexingService]:
    """
    Get the global indexing service instance.

    Returns:
        IndexingService instance or None if not initialized
    """
    return _indexing_service


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
