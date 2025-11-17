"""Service layer for transcription business logic."""

import hashlib
import logging
from datetime import datetime
from typing import Optional

from app.models.transcription import AudioVersion, Conversation, TranscriptionMetadata
from app.repositories.base import TranscriptionRepository
from app.repositories.transcription_index import TranscriptionIndexRepo

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Service for managing transcription business logic."""

    def __init__(
        self,
        repository: TranscriptionRepository,
        index_repo: Optional[TranscriptionIndexRepo] = None,
    ) -> None:
        """
        Initialize the service.

        Args:
            repository: Transcription repository instance
            index_repo: Search index repository (optional)
        """
        self.repository = repository
        self.index_repo = index_repo or TranscriptionIndexRepo()

    async def get_all_conversations(self) -> list[Conversation]:
        """
        Get all conversations grouped from transcriptions.

        This method groups related transcriptions (re-transcriptions of the same audio)
        into conversations with multiple versions.

        Returns:
            List of conversations
        """
        transcriptions = await self.repository.get_all_transcriptions()
        conversations = self._group_transcriptions_into_conversations(transcriptions)
        return conversations

    async def get_conversation_by_id(self, conversation_id: str) -> Conversation | None:
        """
        Get a specific conversation by ID without loading all conversations.

        This method ONLY loads the specific conversation requested using the cache.
        It never falls back to loading all conversations.

        Args:
            conversation_id: Conversation identifier (audio_hash or recording_id/timestamp)

        Returns:
            Conversation or None if not found
        """
        logger.debug(f"Getting conversation by ID: {conversation_id}")

        if not hasattr(self.repository, '_cache'):
            logger.warning("Repository does not support caching, falling back to full load")
            conversations = await self.get_all_conversations()
            for conv in conversations:
                if conv.conversation_id == conversation_id:
                    return conv
            return None

        # Strategy 1: Try as audio_hash (most common case - groups multiple versions)
        matching_entries = self.repository._cache.get_by_audio_hash(conversation_id)
        if matching_entries:
            logger.debug(f"Found {len(matching_entries)} version(s) for audio_hash {conversation_id}")

            # Load all transcriptions for this conversation
            transcriptions = []
            for entry in matching_entries:
                timestamp = int(entry["internal_id"])
                transcription = await self.repository.get_transcription_by_timestamp(timestamp)
                if transcription:
                    transcriptions.append(transcription)

            if transcriptions:
                # Build complete conversation from all versions
                conversations = self._group_transcriptions_into_conversations(transcriptions)
                if conversations:
                    logger.debug(f"Built conversation from {len(transcriptions)} version(s)")
                    return conversations[0]

        # Strategy 2: Try as recording_id (timestamp or recordingId)
        cache_entry = self.repository._cache.get_by_recording_id(conversation_id)
        if cache_entry:
            logger.debug(f"Found cache entry for recording_id: {conversation_id}")
            audio_hash = cache_entry.get("audio_hash")

            # If this entry has an audio_hash, load all versions with that hash
            if audio_hash:
                logger.debug(f"Recording has audio_hash {audio_hash}, loading all versions")
                # Use Strategy 1 to get all versions
                return await self.get_conversation_by_id(audio_hash)

            # No audio_hash means standalone recording
            logger.debug("No audio_hash, loading as standalone recording")
            timestamp = int(cache_entry["internal_id"])
            transcription = await self.repository.get_transcription_by_timestamp(timestamp)
            if transcription:
                conversations = self._group_transcriptions_into_conversations([transcription])
                if conversations:
                    return conversations[0]

        # Strategy 3: Try as internal_id (timestamp)
        cache_entry = self.repository._cache.get_by_internal_id(conversation_id)
        if cache_entry:
            logger.debug(f"Found cache entry for internal_id: {conversation_id}")
            timestamp = int(cache_entry["internal_id"])
            transcription = await self.repository.get_transcription_by_timestamp(timestamp)
            if transcription:
                # Check if this has an audio_hash to load all versions
                if transcription.audio_hash:
                    return await self.get_conversation_by_id(transcription.audio_hash)
                # Standalone
                conversations = self._group_transcriptions_into_conversations([transcription])
                if conversations:
                    return conversations[0]

        logger.warning(f"Conversation not found: {conversation_id}")
        return None

    async def search_conversations(self, query: str) -> list[tuple[Conversation, list[str]]]:
        """
        Search for conversations matching a query.

        Args:
            query: Search query string

        Returns:
            List of tuples (Conversation, list of matching text snippets)
        """
        conversations = await self.get_all_conversations()
        results: list[tuple[Conversation, list[str]]] = []

        query_lower = query.lower()

        for conversation in conversations:
            matches: list[str] = []

            # Search in title
            if query_lower in conversation.title.lower():
                matches.append(f"Title: {conversation.title}")

            # Search in all versions' transcriptions
            for version in conversation.versions:
                trans = version.transcription

                # Search in raw transcription
                if trans.raw_transcription and query_lower in trans.raw_transcription.lower():
                    text = trans.raw_transcription
                    match_contexts = self._extract_match_contexts(text, query, context_chars=100)
                    matches.extend([f"Raw: {ctx}" for ctx in match_contexts])

                # Search in preprocessed transcription
                if (
                    trans.preprocessed_transcription
                    and query_lower in trans.preprocessed_transcription.lower()
                ):
                    text = trans.preprocessed_transcription
                    match_contexts = self._extract_match_contexts(text, query, context_chars=100)
                    matches.extend([f"Preprocessed: {ctx}" for ctx in match_contexts])

                # Search in LLM transcription
                if trans.llm_transcription and query_lower in trans.llm_transcription.lower():
                    match_contexts = self._extract_match_contexts(
                        trans.llm_transcription, query, context_chars=100
                    )
                    matches.extend([f"LLM: {ctx}" for ctx in match_contexts])

                # Search in legacy fields for backward compatibility
                if trans.transcription_text and query_lower in trans.transcription_text.lower():
                    # Skip if already covered by the new fields
                    if not (
                        trans.raw_transcription
                        or trans.preprocessed_transcription
                        or trans.llm_transcription
                    ):
                        text = trans.transcription_text
                        match_contexts = self._extract_match_contexts(
                            text, query, context_chars=100
                        )
                        matches.extend(match_contexts)

                if trans.llm_output and query_lower in trans.llm_output.lower():
                    # Skip if already covered by llm_transcription
                    if not trans.llm_transcription:
                        match_contexts = self._extract_match_contexts(
                            trans.llm_output, query, context_chars=100
                        )
                        matches.extend([f"LLM: {ctx}" for ctx in match_contexts])

            if matches:
                results.append((conversation, matches))

        return results

    async def get_paginated_conversations(
        self, page: int = 1, page_size: int = 30
    ) -> tuple[list[dict], int]:
        """
        Get paginated list of conversations using the search index.

        This is much faster than loading all conversations as it uses the SQLite index.

        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            Tuple of (list of conversation dicts, total count)
        """
        return self.index_repo.get_paginated_conversations(page=page, page_size=page_size)

    async def search_conversations_paginated(
        self, query: str, page: int = 1, page_size: int = 30
    ) -> tuple[list[dict], int]:
        """
        Search conversations with pagination using FTS5.

        This is much faster than the old search method as it uses SQLite FTS5.

        Args:
            query: Search query string
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            Tuple of (list of search result dicts with highlights, total count)
        """
        return self.index_repo.search(query=query, page=page, page_size=page_size)

    async def get_audio_file(self, conversation_id: str, version_id: str) -> bytes:
        """
        Get audio file for a specific conversation version.

        Args:
            conversation_id: Conversation identifier
            version_id: Version identifier (timestamp)

        Returns:
            Audio file bytes

        Raises:
            FileNotFoundError: If conversation or version not found
        """
        conversation = await self.get_conversation_by_id(conversation_id)
        if not conversation:
            raise FileNotFoundError(f"Conversation {conversation_id} not found")

        # Find the specific version
        version = None
        for v in conversation.versions:
            if v.version_id == version_id:
                version = v
                break

        if not version:
            raise FileNotFoundError(
                f"Version {version_id} not found in conversation {conversation_id}"
            )

        return await self.repository.read_audio_file(version.transcription)

    async def get_audio_file_path(self, conversation_id: str, version_id: str) -> str:
        """
        Get audio file path for a specific conversation version.

        Args:
            conversation_id: Conversation identifier
            version_id: Version identifier (timestamp)

        Returns:
            Audio file path

        Raises:
            FileNotFoundError: If conversation or version not found
        """
        conversation = await self.get_conversation_by_id(conversation_id)
        if not conversation:
            raise FileNotFoundError(f"Conversation {conversation_id} not found")

        # Find the specific version
        version = None
        for v in conversation.versions:
            if v.version_id == version_id:
                version = v
                break

        if not version:
            raise FileNotFoundError(
                f"Version {version_id} not found in conversation {conversation_id}"
            )

        if not version.transcription.audio_file:
            raise FileNotFoundError(
                f"No audio file found for version {version_id}"
            )

        return str(version.transcription.audio_file)

    def _group_transcriptions_into_conversations(
        self, transcriptions: list[TranscriptionMetadata]
    ) -> list[Conversation]:
        """
        Group transcriptions into conversations.

        Strategy:
        - For now, group by audio content similarity or metadata hints
        - Each unique recording becomes a conversation
        - Re-transcriptions of the same audio become versions within that conversation

        TODO: Enhance grouping logic based on actual Superwhisper patterns

        Args:
            transcriptions: List of transcription metadata

        Returns:
            List of conversations
        """
        # Group transcriptions by conversation
        # For now, each transcription is its own conversation
        # This will be enhanced when we understand the re-transcription pattern
        conversation_groups: dict[str, list[TranscriptionMetadata]] = {}

        for trans in transcriptions:
            # Generate a conversation ID
            # TODO: Implement proper grouping based on Superwhisper's re-transcription logic
            # For now, each transcription is its own conversation
            conv_id = self._generate_conversation_id(trans)

            if conv_id not in conversation_groups:
                conversation_groups[conv_id] = []

            conversation_groups[conv_id].append(trans)

        # Convert groups to Conversation objects
        conversations: list[Conversation] = []
        for conv_id, trans_list in conversation_groups.items():
            # Sort by timestamp
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
            title = self._generate_conversation_title(trans_list[0])

            conversation = Conversation(
                conversation_id=conv_id,
                title=title,
                versions=versions,
                latest_version=latest_version,
                created_at=trans_list[-1].created_at if trans_list else None,
                updated_at=trans_list[0].created_at if trans_list else None,
            )
            conversations.append(conversation)

        # Sort conversations by most recent update
        conversations.sort(
            key=lambda x: x.updated_at or datetime.min,
            reverse=True,
        )

        return conversations

    def _generate_conversation_id(self, transcription: TranscriptionMetadata) -> str:
        """
        Generate a unique conversation ID.

        Uses audio hash to group re-processed versions of the same recording.
        If audio hash is not available, falls back to timestamp.

        Args:
            transcription: Transcription metadata

        Returns:
            Conversation ID
        """
        # Use audio hash as conversation ID to group versions
        if transcription.audio_hash:
            return transcription.audio_hash

        # Fallback to timestamp if no audio hash available
        # This means each transcription is its own conversation
        return str(transcription.timestamp)

    def _generate_conversation_title(self, transcription: TranscriptionMetadata) -> str:
        """
        Generate a title for the conversation.

        Prefers LLM output over raw transcription.

        Args:
            transcription: Transcription metadata

        Returns:
            Conversation title
        """
        # Try to extract title from transcription
        # Prefer llm > raw > preprocessed > legacy field
        text = (
            transcription.llm_transcription
            or transcription.raw_transcription
            or transcription.preprocessed_transcription
            or transcription.transcription_text
        )

        if text:
            # Use first 50 characters of transcription
            text = text.strip()
            if len(text) > 50:
                return text[:50] + "..."
            return text

        # Fallback to timestamp-based title
        if transcription.created_at:
            return transcription.created_at.strftime("Conversation on %Y-%m-%d %H:%M:%S")

        return f"Conversation {transcription.timestamp}"

    def _extract_match_contexts(
        self, text: str, query: str, context_chars: int = 100
    ) -> list[str]:
        """
        Extract context around query matches in text.

        Args:
            text: Text to search
            query: Query string
            context_chars: Number of characters to include before and after match

        Returns:
            List of text snippets with context around matches
        """
        contexts: list[str] = []
        text_lower = text.lower()
        query_lower = query.lower()

        start = 0
        while True:
            pos = text_lower.find(query_lower, start)
            if pos == -1:
                break

            # Extract context
            context_start = max(0, pos - context_chars)
            context_end = min(len(text), pos + len(query) + context_chars)

            context = text[context_start:context_end]

            # Add ellipsis if needed
            if context_start > 0:
                context = "..." + context
            if context_end < len(text):
                context = context + "..."

            contexts.append(context)
            start = pos + len(query)

            # Limit to 5 matches per text
            if len(contexts) >= 5:
                break

        return contexts
