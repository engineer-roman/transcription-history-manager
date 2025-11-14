"""Repository layer for data access."""

from app.repositories.base import TranscriptionRepository
from app.repositories.superwhisper import SuperwhisperRepository

__all__ = ["TranscriptionRepository", "SuperwhisperRepository"]
