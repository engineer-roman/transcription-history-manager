"""Service layer for transcription business logic."""

import hashlib
from datetime import datetime

from app.models.transcription import AudioVersion, Conversation, TranscriptionMetadata
from app.repositories.base import TranscriptionRepository


class TranscriptionService:
    """Service for managing transcription business logic."""

    def __init__(self, repository: TranscriptionRepository) -> None:
        """
        Initialize the service.

        Args:
            repository: Transcription repository instance
        """
        self.repository = repository

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
        Get a specific conversation by ID.

        Args:
            conversation_id: Conversation identifier

        Returns:
            Conversation or None if not found
        """
        conversations = await self.get_all_conversations()
        for conv in conversations:
            if conv.conversation_id == conversation_id:
                return conv
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

        Prefers preprocessed transcription over raw or LLM versions.

        Args:
            transcription: Transcription metadata

        Returns:
            Conversation title
        """
        # Try to extract title from transcription
        # Prefer preprocessed > raw > llm > legacy field
        text = (
            transcription.preprocessed_transcription
            or transcription.raw_transcription
            or transcription.llm_transcription
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
