"""Repository for managing transcription search index."""

from typing import Optional
import sqlite3
from app.db.database import get_db
from app.models.transcription import TranscriptionMetadata


class TranscriptionIndexRepo:
    """
    Repository for managing the transcription search index.

    Provides efficient full-text search using SQLite FTS5 and
    pagination support for loading transcriptions.
    """

    def upsert(
        self,
        conversation_id: str,
        version_id: str,
        timestamp: int,
        transcription: TranscriptionMetadata,
        title: str,
        is_latest: bool = False,
    ) -> None:
        """
        Insert or update a transcription in the search index.

        Args:
            conversation_id: Unique conversation identifier
            version_id: Version identifier (timestamp as string)
            timestamp: Unix timestamp
            transcription: Transcription metadata object
            title: Conversation title
            is_latest: Whether this is the latest version
        """
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO transcription_index (
                conversation_id, version_id, timestamp, title,
                raw_transcription, preprocessed_transcription, llm_transcription,
                audio_hash, duration, language, model_name, language_model_name,
                mode_name, created_at, is_latest, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(conversation_id, version_id) DO UPDATE SET
                timestamp = excluded.timestamp,
                title = excluded.title,
                raw_transcription = excluded.raw_transcription,
                preprocessed_transcription = excluded.preprocessed_transcription,
                llm_transcription = excluded.llm_transcription,
                audio_hash = excluded.audio_hash,
                duration = excluded.duration,
                language = excluded.language,
                model_name = excluded.model_name,
                language_model_name = excluded.language_model_name,
                mode_name = excluded.mode_name,
                created_at = excluded.created_at,
                is_latest = excluded.is_latest,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                conversation_id,
                version_id,
                timestamp,
                title,
                transcription.raw_transcription,
                transcription.preprocessed_transcription,
                transcription.llm_transcription,
                transcription.audio_hash,
                transcription.duration,
                transcription.language,
                transcription.model_name,
                transcription.language_model_name,
                transcription.mode_name,
                transcription.created_at.isoformat() if transcription.created_at else None,
                1 if is_latest else 0,
            ),
        )

        conn.commit()
        conn.close()

    def get_paginated_conversations(
        self, page: int = 1, page_size: int = 30
    ) -> tuple[list[dict], int]:
        """
        Get paginated list of latest conversations.

        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            Tuple of (list of conversation dicts, total count)
        """
        conn = get_db()
        cursor = conn.cursor()

        # Get total count
        cursor.execute(
            """
            SELECT COUNT(DISTINCT conversation_id)
            FROM transcription_index
            WHERE is_latest = 1
            """
        )
        total = cursor.fetchone()[0]

        # Get paginated results
        offset = (page - 1) * page_size
        cursor.execute(
            """
            SELECT
                conversation_id,
                version_id,
                timestamp,
                title,
                audio_hash,
                duration,
                language,
                created_at,
                updated_at
            FROM transcription_index
            WHERE is_latest = 1
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
            """,
            (page_size, offset),
        )

        rows = cursor.fetchall()
        conn.close()

        results = [dict(row) for row in rows]
        return results, total

    def search(
        self, query: str, page: int = 1, page_size: int = 30
    ) -> tuple[list[dict], int]:
        """
        Full-text search across transcriptions with pagination.

        Args:
            query: Search query string
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            Tuple of (list of search result dicts with highlights, total count)
        """
        conn = get_db()
        cursor = conn.cursor()

        # Prepare FTS5 query - wrap in quotes for phrase search, or use as-is for word search
        # FTS5 automatically handles substring matching with the porter tokenizer
        fts_query = f'"{query}"' if " " in query else query

        # Get total count of matching conversations
        cursor.execute(
            """
            SELECT COUNT(DISTINCT ti.conversation_id)
            FROM transcription_index ti
            INNER JOIN transcription_fts fts ON ti.rowid = fts.rowid
            WHERE transcription_fts MATCH ?
            """,
            (fts_query,),
        )
        total = cursor.fetchone()[0]

        # Get paginated search results with highlights
        offset = (page - 1) * page_size
        cursor.execute(
            """
            SELECT DISTINCT
                ti.conversation_id,
                ti.version_id,
                ti.timestamp,
                ti.title,
                ti.audio_hash,
                ti.duration,
                ti.language,
                ti.created_at,
                ti.updated_at,
                snippet(transcription_fts, 2, '<mark>', '</mark>', '...', 32) as title_snippet,
                snippet(transcription_fts, 3, '<mark>', '</mark>', '...', 64) as raw_snippet,
                snippet(transcription_fts, 4, '<mark>', '</mark>', '...', 64) as preprocessed_snippet,
                snippet(transcription_fts, 5, '<mark>', '</mark>', '...', 64) as llm_snippet,
                bm25(transcription_fts) as rank
            FROM transcription_index ti
            INNER JOIN transcription_fts fts ON ti.rowid = fts.rowid
            WHERE transcription_fts MATCH ?
            ORDER BY rank, ti.timestamp DESC
            LIMIT ? OFFSET ?
            """,
            (fts_query, page_size, offset),
        )

        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            result = dict(row)
            # Collect non-empty snippets
            snippets = []
            for key in ["title_snippet", "raw_snippet", "preprocessed_snippet", "llm_snippet"]:
                snippet = result.pop(key, None)
                if snippet and snippet.strip() and "<mark>" in snippet:
                    snippets.append(snippet)
            result["match_snippets"] = snippets[:5]  # Limit to 5 snippets
            results.append(result)

        return results, total

    def get_by_conversation_id(self, conversation_id: str) -> list[dict]:
        """
        Get all versions of a conversation.

        Args:
            conversation_id: Conversation identifier

        Returns:
            List of version dicts ordered by timestamp (newest first)
        """
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                conversation_id,
                version_id,
                timestamp,
                title,
                raw_transcription,
                preprocessed_transcription,
                llm_transcription,
                audio_hash,
                duration,
                language,
                model_name,
                language_model_name,
                mode_name,
                created_at,
                is_latest
            FROM transcription_index
            WHERE conversation_id = ?
            ORDER BY timestamp DESC
            """,
            (conversation_id,),
        )

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def update_latest_flags(self, conversation_id: str) -> None:
        """
        Update the is_latest flag for all versions of a conversation.
        The version with the highest timestamp gets is_latest=1, others get 0.

        Args:
            conversation_id: Conversation identifier
        """
        conn = get_db()
        cursor = conn.cursor()

        # First, set all to 0
        cursor.execute(
            """
            UPDATE transcription_index
            SET is_latest = 0
            WHERE conversation_id = ?
            """,
            (conversation_id,),
        )

        # Then set the latest one to 1
        cursor.execute(
            """
            UPDATE transcription_index
            SET is_latest = 1
            WHERE conversation_id = ? AND version_id = (
                SELECT version_id
                FROM transcription_index
                WHERE conversation_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
            )
            """,
            (conversation_id, conversation_id),
        )

        conn.commit()
        conn.close()

    def get_count(self) -> int:
        """
        Get total number of unique conversations in the index.

        Returns:
            Count of unique conversations
        """
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(DISTINCT conversation_id)
            FROM transcription_index
            """
        )

        count = cursor.fetchone()[0]
        conn.close()

        return count

    def delete_by_conversation_id(self, conversation_id: str) -> None:
        """
        Delete all versions of a conversation from the index.

        Args:
            conversation_id: Conversation identifier
        """
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM transcription_index
            WHERE conversation_id = ?
            """,
            (conversation_id,),
        )

        conn.commit()
        conn.close()

    def clear_all(self) -> None:
        """Clear all entries from the index."""
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM transcription_index")

        conn.commit()
        conn.close()
