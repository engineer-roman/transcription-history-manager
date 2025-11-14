"""Superwhisper transcription repository implementation."""

import hashlib
import json
from datetime import datetime
from pathlib import Path

import aiofiles

from app.models.transcription import TranscriptionMetadata
from app.repositories.base import TranscriptionRepository
from app.repositories.superwhisper_cache import SuperWhisperCacheRepo


class SuperwhisperRepository(TranscriptionRepository):
    """Repository for Superwhisper transcription files."""

    def __init__(self, base_directory: Path):
        """Initialize repository with base directory and cache."""
        super().__init__(base_directory)
        self.cache = SuperWhisperCacheRepo()

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

    async def get_transcription_by_recording_id(
        self, recording_id: str
    ) -> TranscriptionMetadata | None:
        """
        Retrieve a specific transcription by SuperWhisper recording ID.

        This method uses the cache for faster lookups. If not found in cache,
        it will scan the directory and populate the cache.

        Args:
            recording_id: SuperWhisper recording ID

        Returns:
            Transcription metadata or None if not found
        """
        # Try cache first
        cache_entry = self.cache.get_by_recording_id(recording_id)
        if cache_entry:
            # Load from cached directory path
            timestamp = int(cache_entry["internal_id"])
            return await self.get_transcription_by_timestamp(timestamp)

        # If not in cache, scan all transcriptions to populate cache
        # This will also populate the cache with this recording if it exists
        await self.get_all_transcriptions()

        # Try cache again
        cache_entry = self.cache.get_by_recording_id(recording_id)
        if cache_entry:
            timestamp = int(cache_entry["internal_id"])
            return await self.get_transcription_by_timestamp(timestamp)

        return None

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

        SuperWhisper structure:
        - Directory name: Unix timestamp (e.g., 1762651071)
        - Files: meta.json, output.wav

        Args:
            directory: Directory containing transcription files
            timestamp: Unix timestamp

        Returns:
            TranscriptionMetadata or None if loading fails
        """
        # Look for audio file - SuperWhisper uses output.wav
        audio_file = directory / "output.wav"
        if not audio_file.exists():
            # Fallback to legacy naming or other extensions
            for filename in ["audio.wav", "output.mp3", "audio.mp3", "output.m4a", "audio.m4a"]:
                potential_audio = directory / filename
                if potential_audio.exists():
                    audio_file = potential_audio
                    break
            else:
                audio_file = None

        # Look for metadata file - SuperWhisper uses meta.json
        metadata_file = directory / "meta.json"
        if not metadata_file.exists():
            # Fallback to legacy naming
            metadata_file = directory / "metadata.json"

        metadata_content = None
        if metadata_file.exists():
            try:
                async with aiofiles.open(metadata_file, "r", encoding="utf-8") as f:
                    content = await f.read()
                    metadata_content = json.loads(content)
            except (json.JSONDecodeError, OSError):
                pass

        # Extract transcription data from SuperWhisper meta.json
        raw_transcription = None
        preprocessed_transcription = None
        llm_transcription = None
        segments = None
        duration = None
        language = None
        model_name = None
        language_model_name = None
        mode_name = None
        processing_time = None

        recording_id = None
        if metadata_content:
            # SuperWhisper fields
            recording_id = metadata_content.get("recordingId") or metadata_content.get("id")
            raw_transcription = metadata_content.get("rawResult")
            preprocessed_transcription = metadata_content.get("result")
            llm_transcription = metadata_content.get("llmResult")
            segments = metadata_content.get("segments")
            duration = metadata_content.get("duration")
            language = metadata_content.get("languageSelected")
            model_name = metadata_content.get("modelName")
            language_model_name = metadata_content.get("languageModelName")
            mode_name = metadata_content.get("modeName")
            processing_time = metadata_content.get("processingTime")

        # Calculate audio hash for version detection
        audio_hash = None
        if audio_file and audio_file.exists():
            audio_hash = await self._calculate_audio_hash(audio_file)

        # Parse datetime from meta.json or use timestamp
        created_at = None
        if metadata_content and "datetime" in metadata_content:
            try:
                # SuperWhisper format: "2025-11-13T01:42:15"
                datetime_str = metadata_content["datetime"]
                created_at = datetime.fromisoformat(datetime_str)
            except (ValueError, TypeError):
                pass

        if not created_at:
            created_at = datetime.fromtimestamp(timestamp)

        # Determine best transcription_text for backward compatibility
        # Prefer preprocessed > raw > llm
        transcription_text = preprocessed_transcription or raw_transcription or llm_transcription

        # Cache the mapping between recording_id and timestamp
        if recording_id:
            self.cache.upsert(
                recording_id=recording_id,
                internal_id=str(timestamp),
                directory_path=str(directory),
                audio_hash=audio_hash,
            )

        return TranscriptionMetadata(
            timestamp=timestamp,
            directory=directory,
            audio_file=audio_file if audio_file and audio_file.exists() else None,
            metadata_file=metadata_file if metadata_file.exists() else None,
            recording_id=recording_id,
            raw_transcription=raw_transcription,
            preprocessed_transcription=preprocessed_transcription,
            llm_transcription=llm_transcription,
            transcription_text=transcription_text,
            segments=segments,
            transcription_with_timecodes=segments,  # Legacy field
            llm_output=llm_transcription,  # Legacy field
            duration=duration,
            language=language,
            model_name=model_name,
            language_model_name=language_model_name,
            mode_name=mode_name,
            processing_time=processing_time,
            audio_hash=audio_hash,
            created_at=created_at,
        )

    async def _calculate_audio_hash(self, audio_file: Path) -> str:
        """
        Calculate SHA256 hash of audio file for version detection.

        This allows us to identify when different recordings are re-processed
        versions of the same audio.

        Args:
            audio_file: Path to audio file

        Returns:
            SHA256 hash as hex string
        """
        sha256_hash = hashlib.sha256()
        try:
            async with aiofiles.open(audio_file, "rb") as f:
                # Read in chunks to handle large files
                while chunk := await f.read(8192):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except OSError:
            # If we can't read the file, return empty hash
            return ""
