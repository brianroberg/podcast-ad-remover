import sqlite3
from pathlib import Path


class StateManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    feed_url TEXT NOT NULL,
                    episode_guid TEXT NOT NULL,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ad_segments_found INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'success',
                    UNIQUE(feed_url, episode_guid)
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def is_processed(self, feed_url: str, episode_guid: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM processed_episodes WHERE feed_url = ? AND episode_guid = ?",
                (feed_url, episode_guid),
            )
            return cursor.fetchone() is not None

    def mark_processed(
        self,
        feed_url: str,
        episode_guid: str,
        ad_segments_found: int = 0,
        status: str = "success",
    ):
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO processed_episodes
                    (feed_url, episode_guid, ad_segments_found, status)
                VALUES (?, ?, ?, ?)
                """,
                (feed_url, episode_guid, ad_segments_found, status),
            )
