"""SQLite database connection and initialization."""

import sqlite3
from pathlib import Path
from typing import Optional

# Database file path
DB_PATH = Path("transcription_cache.db")


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

    conn.commit()
    conn.close()
