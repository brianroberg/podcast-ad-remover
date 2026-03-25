import sqlite3

import pytest

from podcast_ad_remover.state import StateManager


@pytest.fixture
def state_db(tmp_path):
    db_path = tmp_path / "state.db"
    return StateManager(db_path)


class TestStateManager:
    def test_init_creates_table(self, state_db):
        conn = sqlite3.connect(state_db.db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='processed_episodes'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_is_processed_returns_false_for_unknown(self, state_db):
        assert state_db.is_processed("https://example.com/feed.xml", "ep-1") is False

    def test_mark_processed_then_is_processed(self, state_db):
        state_db.mark_processed("https://example.com/feed.xml", "ep-1", ad_segments_found=2)
        assert state_db.is_processed("https://example.com/feed.xml", "ep-1") is True

    def test_different_feeds_same_guid(self, state_db):
        state_db.mark_processed("https://example.com/feed1.xml", "ep-1", ad_segments_found=0)
        assert state_db.is_processed("https://example.com/feed1.xml", "ep-1") is True
        assert state_db.is_processed("https://example.com/feed2.xml", "ep-1") is False

    def test_mark_processed_with_fallback_status(self, state_db):
        state_db.mark_processed(
            "https://example.com/feed.xml", "ep-1", ad_segments_found=0, status="fallback"
        )
        assert state_db.is_processed("https://example.com/feed.xml", "ep-1") is True

    def test_mark_processed_duplicate_is_ignored(self, state_db):
        state_db.mark_processed("https://example.com/feed.xml", "ep-1", ad_segments_found=2)
        state_db.mark_processed("https://example.com/feed.xml", "ep-1", ad_segments_found=3)
        assert state_db.is_processed("https://example.com/feed.xml", "ep-1") is True
