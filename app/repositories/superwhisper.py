"""Superwhisper transcription repository implementation."""

import hashlib
import json
import logging
from datetime import datetime
from logly import logger
from pathlib import Path

import aiofiles

from app.models.transcription import TranscriptionMetadata
from app.repositories.base import TranscriptionRepository
from app.repositories.superwhisper_cache import SuperWhisperCacheRepo

logger = logging.getLogger(__name__)


class SuperwhisperRepository(TranscriptionRepository):
    """Repository for Superwhisper transcription files."""

    def __init__(self, base_directory: Path):
        """Initialize repository with base directory and cache."""
        super().__init__(base_directory)
        self._cache = SuperWhisperCacheRepo()

    async def get_all_transcriptions(self) -> list[TranscriptionMetadata]:
        """
        Retrieve all transcriptions from Superwhisper directory.

        This method optimizes loading by checking if the cache is up-to-date.
        It compares the number of directories with the number of cache entries.
        If they match, it loads from cache without scanning the directory.

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
        if not self.base_directory.exists():
            logger.warning(f"Base directory does not exist: {self.base_directory}")
            return []

        # Count directories and cache entries
        dir_count = self._count_timestamp_directories()
        cache_count = len(self._cache.get_all())

        logger.info(f"Directory count: {dir_count}, Cache count: {cache_count}")

        # If counts match, load from cache
        if dir_count == cache_count and cache_count > 0:
            logger.info("Cache is up-to-date, loading from cache")
            return await self._load_from_cache()

        # Counts differ, need to refresh cache by scanning directory
        logger.warning(f"Cache out of sync (dirs: {dir_count}, cache: {cache_count}), refreshing cache")
        return await self._load_from_directory_and_update_cache()

    def _count_timestamp_directories(self) -> int:
        """
        Count the number of valid timestamp directories in base directory.

        Returns:
            Number of directories with timestamp names
        """
        count = 0
        if not self.base_directory.exists():
            return count

        for subdir in self.base_directory.iterdir():
            if not subdir.is_dir():
                continue

            # Try to parse directory name as timestamp
            try:
                int(subdir.name)
                count += 1
            except ValueError:
                # Skip directories that aren't timestamps
                continue

        return count

    async def _load_from_cache(self) -> list[TranscriptionMetadata]:
        """
        Load all transcriptions from cache without scanning the directory.

        Returns:
            List of transcription metadata loaded from cache
        """
        transcriptions: list[TranscriptionMetadata] = []
        cache_entries = self._cache.get_all()

        logger.debug(f"Loading {len(cache_entries)} transcriptions from cache")

        for entry in cache_entries:
            try:
                timestamp = int(entry["internal_id"])
                directory_path = Path(entry["directory_path"])

                # Load transcription from the cached directory path
                if directory_path.exists() and directory_path.is_dir():
                    transcription = await self._load_transcription_from_directory(
                        directory_path, timestamp
                    )
                    if transcription:
                        transcriptions.append(transcription)
                else:
                    logger.warning(f"Cached directory not found: {directory_path}, will refresh cache")
                    # Directory doesn't exist, cache is stale, fall back to full scan
                    return await self._load_from_directory_and_update_cache()
            except (ValueError, KeyError) as e:
                logger.warning(f"Invalid cache entry: {e}, skipping")
                continue

        # Sort by timestamp (newest first)
        transcriptions.sort(key=lambda x: x.timestamp, reverse=True)
        logger.info(f"Loaded {len(transcriptions)} transcriptions from cache")
        return transcriptions

    async def _load_from_directory_and_update_cache(self) -> list[TranscriptionMetadata]:
        """
        Load all transcriptions by scanning the directory and update the cache.

        Returns:
            List of transcription metadata
        """
        transcriptions: list[TranscriptionMetadata] = []

        logger.debug("Scanning directory for transcriptions")

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
        logger.info(f"Scanned and loaded {len(transcriptions)} transcriptions from directory")
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
        cache_entry = self._cache.get_by_recording_id(recording_id)
        logger.info(f"Recording cache state {recording_id}: {bool(cache_entry)}")
        if cache_entry:
            logger.debug(f"Cache hit for recording_id={recording_id}, internal_id={cache_entry['internal_id']}")
            # Load from cached directory path
            timestamp = int(cache_entry["internal_id"])
            return await self.get_transcription_by_timestamp(timestamp)

        # If not in cache, scan all transcriptions to populate cache
        # This will also populate the cache with this recording if it exists
        logger.warning(f"Cache miss for recording_id={recording_id}, scanning all transcriptions to populate cache")
        await self.get_all_transcriptions()

        # Try cache again
        cache_entry = self._cache.get_by_recording_id(recording_id)
        if cache_entry:
            logger.debug(f"Found recording_id={recording_id} after cache population")
            timestamp = int(cache_entry["internal_id"])
            return await self.get_transcription_by_timestamp(timestamp)

        logger.warning(f"Recording not found: recording_id={recording_id}")
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
            raw_segments = metadata_content.get("segments")

            # Normalize segment field names
            # SuperWhisper uses 'start'/'end' but we expect 'start_time'/'end_time'
            segments = self._normalize_segments(raw_segments) if raw_segments else None

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
            self._cache.upsert(
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

    def _normalize_segments(self, segments: list[dict]) -> list[dict]:
        """
        Normalize segment field names to match our expected format.

        SuperWhisper segments use 'start'/'end' but we expect 'start_time'/'end_time'.
        This method transforms the segments to use consistent field names.

        Args:
            segments: Raw segments from SuperWhisper

        Returns:
            Normalized segments with start_time, end_time, and text fields
        """
        if not segments:
            return []

        normalized = []
        for segment in segments:
            normalized_segment = {
                "start_time": segment.get("start", 0),
                "end_time": segment.get("end", 0),
                "text": segment.get("text", ""),
            }
            normalized.append(normalized_segment)

        return normalized
