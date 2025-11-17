"""SQLite database connection and initialization."""

import sqlite3
from pathlib import Path
from typing import Optional

# Database file path - store in project root
# Go up from app/db/database.py to project root
DB_PATH = Path(__file__).parent.parent.parent / "transcription_cache.db"


def get_db() -> sqlite3.Connection:
    """
    Get or create a SQLite database connection.

    Returns:
        SQLite connection object
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn


def init_db() -> None:
    """
    Initialize the database with required tables.

    Creates tables if they don't exist:
    - superwhisper_cache: Maps SuperWhisper recording IDs to internal IDs
    - transcription_index: Stores transcription metadata for fast querying
    - transcription_fts: FTS5 virtual table for full-text search
    """
    conn = get_db()
    cursor = conn.cursor()

    # Create superwhisper_cache table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS superwhisper_cache (
            recording_id TEXT PRIMARY KEY,
            internal_id TEXT NOT NULL,
            directory_path TEXT NOT NULL,
            audio_hash TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Create index on internal_id for faster lookups
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_internal_id
        ON superwhisper_cache(internal_id)
        """
    )

    # Create index on audio_hash for faster lookups
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_audio_hash
        ON superwhisper_cache(audio_hash)
        """
    )

    # Create transcription_index table for metadata
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS transcription_index (
            conversation_id TEXT NOT NULL,
            version_id TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            title TEXT,
            raw_transcription TEXT,
            preprocessed_transcription TEXT,
            llm_transcription TEXT,
            audio_hash TEXT,
            duration REAL,
            language TEXT,
            model_name TEXT,
            language_model_name TEXT,
            mode_name TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_latest INTEGER DEFAULT 0,
            PRIMARY KEY (conversation_id, version_id)
        )
        """
    )

    # Create indexes for common queries
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_transcription_conversation_id
        ON transcription_index(conversation_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_transcription_timestamp
        ON transcription_index(timestamp DESC)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_transcription_audio_hash
        ON transcription_index(audio_hash)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_transcription_is_latest
        ON transcription_index(is_latest)
        """
    )

    # Create FTS5 virtual table for full-text search
    # FTS5 provides efficient substring matching and result highlighting
    cursor.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS transcription_fts USING fts5(
            conversation_id UNINDEXED,
            version_id UNINDEXED,
            title,
            raw_transcription,
            preprocessed_transcription,
            llm_transcription,
            content='transcription_index',
            content_rowid='rowid',
            tokenize='porter unicode61 remove_diacritics 2'
        )
        """
    )

    # Create triggers to keep FTS5 table in sync with main table
    cursor.execute(
        """
        CREATE TRIGGER IF NOT EXISTS transcription_index_ai AFTER INSERT ON transcription_index BEGIN
            INSERT INTO transcription_fts(rowid, conversation_id, version_id, title, raw_transcription, preprocessed_transcription, llm_transcription)
            VALUES (new.rowid, new.conversation_id, new.version_id, new.title, new.raw_transcription, new.preprocessed_transcription, new.llm_transcription);
        END
        """
    )

    cursor.execute(
        """
        CREATE TRIGGER IF NOT EXISTS transcription_index_ad AFTER DELETE ON transcription_index BEGIN
            INSERT INTO transcription_fts(transcription_fts, rowid, conversation_id, version_id, title, raw_transcription, preprocessed_transcription, llm_transcription)
            VALUES ('delete', old.rowid, old.conversation_id, old.version_id, old.title, old.raw_transcription, old.preprocessed_transcription, old.llm_transcription);
        END
        """
    )

    cursor.execute(
        """
        CREATE TRIGGER IF NOT EXISTS transcription_index_au AFTER UPDATE ON transcription_index BEGIN
            INSERT INTO transcription_fts(transcription_fts, rowid, conversation_id, version_id, title, raw_transcription, preprocessed_transcription, llm_transcription)
            VALUES ('delete', old.rowid, old.conversation_id, old.version_id, old.title, old.raw_transcription, old.preprocessed_transcription, old.llm_transcription);
            INSERT INTO transcription_fts(rowid, conversation_id, version_id, title, raw_transcription, preprocessed_transcription, llm_transcription)
            VALUES (new.rowid, new.conversation_id, new.version_id, new.title, new.raw_transcription, new.preprocessed_transcription, new.llm_transcription);
        END
        """
    )

    conn.commit()
    conn.close()
