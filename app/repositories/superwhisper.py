"""Superwhisper transcription repository implementation."""

import json
from datetime import datetime
from pathlib import Path

import aiofiles

from app.models.transcription import TranscriptionMetadata
from app.repositories.base import TranscriptionRepository


class SuperwhisperRepository(TranscriptionRepository):
    """Repository for Superwhisper transcription files."""

    async def get_all_transcriptions(self) -> list[TranscriptionMetadata]:
        """
        Retrieve all transcriptions from Superwhisper directory.

        Expected structure:
        base_directory/
          ├── 1234567890/  (Unix timestamp)
          │   ├── metadata.json
          │   ├── audio.wav
          │   └── ...
          ├── 1234567891/
          │   └── ...

        Returns:
            List of transcription metadata
        """
        transcriptions: list[TranscriptionMetadata] = []

        if not self.base_directory.exists():
            return transcriptions

        # Iterate through subdirectories
        for subdir in self.base_directory.iterdir():
            if not subdir.is_dir():
                continue

            # Try to parse directory name as timestamp
            try:
                timestamp = int(subdir.name)
            except ValueError:
                # Skip directories that aren't timestamps
                continue

            transcription = await self._load_transcription_from_directory(
                subdir, timestamp
            )
            if transcription:
                transcriptions.append(transcription)

        # Sort by timestamp (newest first)
        transcriptions.sort(key=lambda x: x.timestamp, reverse=True)
        return transcriptions

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
        subdir = self.base_directory / str(timestamp)
        if not subdir.exists() or not subdir.is_dir():
            return None

        return await self._load_transcription_from_directory(subdir, timestamp)

    async def read_audio_file(self, transcription: TranscriptionMetadata) -> bytes:
        """
        Read the audio file for a transcription.

        Args:
            transcription: Transcription metadata

        Returns:
            Audio file bytes

        Raises:
            FileNotFoundError: If audio file doesn't exist
        """
        if not transcription.audio_file:
            raise FileNotFoundError(
                f"No audio file found for transcription {transcription.timestamp}"
            )

        async with aiofiles.open(transcription.audio_file, "rb") as f:
            return await f.read()

    async def _load_transcription_from_directory(
        self, directory: Path, timestamp: int
    ) -> TranscriptionMetadata | None:
        """
        Load transcription metadata from a directory.

        Args:
            directory: Directory containing transcription files
            timestamp: Unix timestamp

        Returns:
            TranscriptionMetadata or None if loading fails
        """
        # Look for audio file (try different extensions)
        audio_file = None
        for extension in [".wav", ".mp3", ".m4a", ".ogg"]:
            potential_audio = directory / f"audio{extension}"
            if potential_audio.exists():
                audio_file = potential_audio
                break

        # Look for metadata file
        metadata_file = directory / "metadata.json"
        metadata_content = None
        if metadata_file.exists():
            try:
                async with aiofiles.open(metadata_file, "r", encoding="utf-8") as f:
                    content = await f.read()
                    metadata_content = json.loads(content)
            except (json.JSONDecodeError, OSError):
                pass

        # Extract transcription data from metadata
        raw_transcription = None
        timecodes = None
        llm_output = None
        duration = None

        if metadata_content:
            raw_transcription = metadata_content.get("transcription")
            timecodes = metadata_content.get("timecodes")
            llm_output = metadata_content.get("llm_output")
            duration = metadata_content.get("duration")

        # Create TranscriptionMetadata
        created_at = datetime.fromtimestamp(timestamp)

        return TranscriptionMetadata(
            timestamp=timestamp,
            directory=directory,
            audio_file=audio_file,
            metadata_file=metadata_file if metadata_file.exists() else None,
            transcription_text=raw_transcription,
            transcription_with_timecodes=timecodes,
            llm_output=llm_output,
            duration=duration,
            created_at=created_at,
        )
