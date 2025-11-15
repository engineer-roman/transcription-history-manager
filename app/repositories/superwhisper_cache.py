"""Repository for caching SuperWhisper recording ID mappings."""

from typing import Optional
import sqlite3
from app.db.database import get_db


class SuperWhisperCacheRepo:
    """
    Repository for managing SuperWhisper recording ID cache.

    Caches the mapping between SuperWhisper's internal recording IDs
    and the IDs used in our application (timestamps).
    """

    def get_by_recording_id(self, recording_id: str) -> Optional[dict]:
        """
        Get cache entry by SuperWhisper recording ID.

        Args:
            recording_id: SuperWhisper recording ID

        Returns:
            Cache entry dict or None if not found
        """
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT recording_id, internal_id, directory_path, audio_hash, created_at, updated_at
            FROM superwhisper_cache
            WHERE recording_id = ?
            """,
            (recording_id,),
        )

        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def get_by_internal_id(self, internal_id: str) -> Optional[dict]:
        """
        Get cache entry by internal ID (timestamp).

        Args:
            internal_id: Internal ID (timestamp)

        Returns:
            Cache entry dict or None if not found
        """
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT recording_id, internal_id, directory_path, audio_hash, created_at, updated_at
            FROM superwhisper_cache
            WHERE internal_id = ?
            """,
            (internal_id,),
        )

        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def get_by_audio_hash(self, audio_hash: str) -> list[dict]:
        """
        Get all cache entries with the given audio hash.

        Args:
            audio_hash: Audio file hash

        Returns:
            List of cache entry dicts with matching audio_hash
        """
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT recording_id, internal_id, directory_path, audio_hash, created_at, updated_at
            FROM superwhisper_cache
            WHERE audio_hash = ?
            ORDER BY created_at DESC
            """,
            (audio_hash,),
        )

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_all(self) -> list[dict]:
        """
        Get all cache entries.

        Returns:
            List of cache entry dicts
        """
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT recording_id, internal_id, directory_path, audio_hash, created_at, updated_at
            FROM superwhisper_cache
            ORDER BY created_at DESC
            """
        )

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def upsert(
        self,
        recording_id: str,
        internal_id: str,
        directory_path: str,
        audio_hash: Optional[str] = None,
    ) -> None:
        """
        Insert or update a cache entry.

        Args:
            recording_id: SuperWhisper recording ID
            internal_id: Internal ID (timestamp)
            directory_path: Path to the recording directory
            audio_hash: Optional audio file hash
        """
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO superwhisper_cache (recording_id, internal_id, directory_path, audio_hash, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(recording_id) DO UPDATE SET
                internal_id = excluded.internal_id,
                directory_path = excluded.directory_path,
                audio_hash = excluded.audio_hash,
                updated_at = CURRENT_TIMESTAMP
            """,
            (recording_id, internal_id, directory_path, audio_hash),
        )

        conn.commit()
        conn.close()

    def delete(self, recording_id: str) -> None:
        """
        Delete a cache entry by recording ID.

        Args:
            recording_id: SuperWhisper recording ID
        """
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM superwhisper_cache
            WHERE recording_id = ?
            """,
            (recording_id,),
        )

        conn.commit()
        conn.close()

    def clear_all(self) -> None:
        """Clear all cache entries."""
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM superwhisper_cache")

        conn.commit()
        conn.close()
