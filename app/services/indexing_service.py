"""Background indexing service for transcription search."""

import asyncio
import logging
from typing import Optional

from app.models.transcription import Conversation, TranscriptionMetadata
from app.repositories.base import TranscriptionRepository
from app.repositories.transcription_index import TranscriptionIndexRepo

logger = logging.getLogger(__name__)


class IndexingService:
    """
    Background service for indexing transcriptions into the search database.

    This service syncs transcriptions from the file system into the SQLite
    FTS5 index for fast full-text search and pagination.
    """

    def __init__(
        self,
        transcription_repo: TranscriptionRepository,
        index_repo: Optional[TranscriptionIndexRepo] = None,
    ) -> None:
        """
        Initialize the indexing service.

        Args:
            transcription_repo: Repository for reading transcription files
            index_repo: Repository for managing the search index
        """
        self.transcription_repo = transcription_repo
        self.index_repo = index_repo or TranscriptionIndexRepo()
        self._sync_task: Optional[asyncio.Task] = None
        self._is_syncing = False
        self._sync_complete = False

    async def start_background_sync(self) -> None:
        """
        Start background synchronization of transcriptions to the search index.

        This is non-blocking and runs in the background.
        """
        if self._sync_task is not None and not self._sync_task.done():
            logger.info("Sync task already running")
            return

        logger.info("Starting background sync task")
        self._sync_task = asyncio.create_task(self._sync_all_transcriptions())

    async def wait_for_sync(self, timeout: float = 30.0) -> bool:
        """
        Wait for the background sync to complete.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if sync completed, False if timed out
        """
        if self._sync_complete:
            return True

        if self._sync_task is None:
            return False

        try:
            await asyncio.wait_for(self._sync_task, timeout=timeout)
            return True
        except asyncio.TimeoutError:
            logger.warning(f"Sync did not complete within {timeout}s")
            return False

    def is_syncing(self) -> bool:
        """Check if sync is currently in progress."""
        return self._is_syncing

    def is_sync_complete(self) -> bool:
        """Check if initial sync has completed."""
        return self._sync_complete

    async def ensure_sync(self, force: bool = False) -> bool:
        """
        Ensure the index is synchronized with the file system.

        Checks if there are new recordings and triggers sync if needed.
        This is safe to call multiple times and will skip if already syncing.

        Args:
            force: Force a full re-sync even if counts match

        Returns:
            True if sync was performed, False if skipped
        """
        # Skip if already syncing
        if self._is_syncing:
            logger.debug("Sync already in progress, skipping ensure_sync")
            return False

        # Check if sync is needed
        if not force:
            needs_sync = await self._check_sync_needed()
            if not needs_sync:
                logger.debug("Index is up-to-date, skipping sync")
                return False

        logger.info("Index out of sync, triggering re-sync")
        await self._sync_all_transcriptions()
        return True

    async def _check_sync_needed(self) -> bool:
        """
        Check if synchronization is needed by comparing file system and database.

        Returns:
            True if sync is needed, False if index is up-to-date
        """
        try:
            # Count directories in file system
            from pathlib import Path
            base_dir = self.transcription_repo.base_directory
            if not base_dir.exists():
                return False

            dir_count = 0
            for subdir in base_dir.iterdir():
                if subdir.is_dir():
                    try:
                        int(subdir.name)
                        dir_count += 1
                    except ValueError:
                        continue

            # Count indexed conversations in database
            db_count = self.index_repo.get_count()

            logger.debug(f"Sync check: {dir_count} directories vs {db_count} indexed conversations")

            # Need sync if counts don't match
            return dir_count != db_count

        except Exception as e:
            logger.error(f"Error checking sync status: {e}", exc_info=True)
            # On error, trigger sync to be safe
            return True

    async def _sync_all_transcriptions(self) -> None:
        """
        Sync all transcriptions from file system to search index.

        This method:
        1. Loads all transcriptions from the file system
        2. Groups them into conversations
        3. Indexes each conversation and version into the search database
        """
        try:
            self._is_syncing = True
            logger.info("Starting transcription sync")

            # Get all transcriptions from the repository
            transcriptions = await self.transcription_repo.get_all_transcriptions()
            logger.info(f"Found {len(transcriptions)} transcriptions to index")

            # Group transcriptions into conversations
            conversations = self._group_transcriptions_into_conversations(transcriptions)
            logger.info(f"Grouped into {len(conversations)} conversations")

            # Index each conversation
            indexed_count = 0
            for conversation in conversations:
                await self._index_conversation(conversation)
                indexed_count += 1

                # Log progress every 100 conversations
                if indexed_count % 100 == 0:
                    logger.info(f"Indexed {indexed_count}/{len(conversations)} conversations")

            logger.info(f"Sync complete: indexed {indexed_count} conversations")
            self._sync_complete = True

        except Exception as e:
            logger.error(f"Error during sync: {e}", exc_info=True)
            raise
        finally:
            self._is_syncing = False

    async def _index_conversation(self, conversation: Conversation) -> None:
        """
        Index a single conversation and all its versions.

        Args:
            conversation: Conversation to index
        """
        try:
            # Index each version
            for version in conversation.versions:
                title = self._generate_title(version.transcription)
                self.index_repo.upsert(
                    conversation_id=conversation.conversation_id,
                    version_id=version.version_id,
                    timestamp=version.timestamp,
                    transcription=version.transcription,
                    title=title,
                    is_latest=version.is_latest,
                )

            # Update is_latest flags to ensure only the latest version is marked
            self.index_repo.update_latest_flags(conversation.conversation_id)

        except Exception as e:
            logger.error(
                f"Error indexing conversation {conversation.conversation_id}: {e}",
                exc_info=True,
            )

    def _group_transcriptions_into_conversations(
        self, transcriptions: list[TranscriptionMetadata]
    ) -> list[Conversation]:
        """
        Group transcriptions into conversations.

        This mirrors the logic from TranscriptionService to ensure consistency.

        Args:
            transcriptions: List of transcription metadata

        Returns:
            List of conversations
        """
        from app.models.transcription import AudioVersion, Conversation
        from datetime import datetime

        conversation_groups: dict[str, list[TranscriptionMetadata]] = {}

        for trans in transcriptions:
            conv_id = self._generate_conversation_id(trans)
            if conv_id not in conversation_groups:
                conversation_groups[conv_id] = []
            conversation_groups[conv_id].append(trans)

        conversations: list[Conversation] = []
        for conv_id, trans_list in conversation_groups.items():
            # Sort by timestamp (newest first)
            trans_list.sort(key=lambda x: x.timestamp, reverse=True)

            # Create versions
            versions: list[AudioVersion] = []
            for idx, trans in enumerate(trans_list):
                is_latest = idx == 0
                version = AudioVersion(
                    version_id=str(trans.timestamp),
                    timestamp=trans.timestamp,
                    transcription=trans,
                    is_latest=is_latest,
                )
                versions.append(version)

            # Create conversation
            latest_version = versions[0] if versions else None
            title = self._generate_title(trans_list[0])

            conversation = Conversation(
                conversation_id=conv_id,
                title=title,
                versions=versions,
                latest_version=latest_version,
                created_at=trans_list[-1].created_at if trans_list else None,
                updated_at=trans_list[0].created_at if trans_list else None,
            )
            conversations.append(conversation)

        # Sort by most recent update
        conversations.sort(
            key=lambda x: x.updated_at or datetime.min,
            reverse=True,
        )

        return conversations

    def _generate_conversation_id(self, transcription: TranscriptionMetadata) -> str:
        """
        Generate a unique conversation ID.

        Uses audio hash to group re-processed versions of the same recording.

        Args:
            transcription: Transcription metadata

        Returns:
            Conversation ID
        """
        if transcription.audio_hash:
            return transcription.audio_hash
        return str(transcription.timestamp)

    def _generate_title(self, transcription: TranscriptionMetadata) -> str:
        """
        Generate a title for the conversation.

        Args:
            transcription: Transcription metadata

        Returns:
            Conversation title
        """
        from datetime import datetime

        text = (
            transcription.llm_transcription
            or transcription.raw_transcription
            or transcription.preprocessed_transcription
            or transcription.transcription_text
        )

        if text:
            text = text.strip()
            if len(text) > 50:
                return text[:50] + "..."
            return text

        if transcription.created_at:
            return transcription.created_at.strftime("Conversation on %Y-%m-%d %H:%M:%S")

        return f"Conversation {transcription.timestamp}"
