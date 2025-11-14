"""Base repository interface for transcription providers."""

from abc import ABC, abstractmethod
from pathlib import Path

from app.models.transcription import TranscriptionMetadata


class TranscriptionRepository(ABC):
    """Abstract base class for transcription repositories."""

    def __init__(self, base_directory: Path) -> None:
        """
        Initialize the repository.

        Args:
            base_directory: Base directory containing transcription files
        """
        self.base_directory = base_directory

    @abstractmethod
    async def get_all_transcriptions(self) -> list[TranscriptionMetadata]:
        """
        Retrieve all transcriptions from the repository.

        Returns:
            List of transcription metadata
        """
        pass

    @abstractmethod
    async def get_transcription_by_timestamp(
        self, timestamp: int
    ) -> TranscriptionMetadata | None:
        """
        Retrieve a specific transcription by timestamp.

        Args:
            timestamp: Unix timestamp identifying the transcription

        Returns:
            Transcription metadata or None if not found
        """
        pass

    @abstractmethod
    async def read_audio_file(self, transcription: TranscriptionMetadata) -> bytes:
        """
        Read the audio file for a transcription.

        Args:
            transcription: Transcription metadata

        Returns:
            Audio file bytes
        """
        pass
