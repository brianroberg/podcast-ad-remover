from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from podcast_ad_remover.models import AppConfig, AudiobookshelfConfig, Episode, FeedConfig
from podcast_ad_remover.scheduler import Scheduler


@pytest.fixture
def app_config():
    return AppConfig(
        audiobookshelf=AudiobookshelfConfig(url="http://abs:13378", library_id="lib-1"),
        feeds=[
            FeedConfig(url="https://example.com/feed.xml"),
            FeedConfig(url="https://example.com/other.xml", name="Custom", poll_interval_hours=1),
        ],
        default_poll_interval_hours=12.0,
    )


@pytest.fixture
def scheduler(app_config):
    with patch("podcast_ad_remover.scheduler.genai") as mock_genai:
        mock_genai.Client.return_value = MagicMock()
        return Scheduler(
            config=app_config, abs_api_key="abs-key", gemini_api_key="gem-key",
            data_dir="/tmp/test-data",
        )


class TestScheduler:
    def test_effective_poll_interval(self, scheduler):
        assert scheduler._effective_interval_seconds(scheduler.config.feeds[0]) == 12.0 * 3600
        assert scheduler._effective_interval_seconds(scheduler.config.feeds[1]) == 1.0 * 3600

    @patch("podcast_ad_remover.scheduler.parse_feed")
    @patch("podcast_ad_remover.scheduler.process_episode")
    def test_poll_feed_processes_new_episodes(self, mock_process, mock_parse, scheduler):
        mock_parse.return_value = (
            "Test Podcast",
            "A test podcast",
            [
                Episode(guid="ep-1", title="Ep 1", audio_url="https://example.com/ep1.mp3"),
                Episode(guid="ep-2", title="Ep 2", audio_url="https://example.com/ep2.mp3"),
            ],
        )
        mock_process.return_value = True
        feed = FeedConfig(url="https://example.com/feed.xml")
        scheduler.poll_feed(feed)
        assert mock_process.call_count == 2

    @patch("podcast_ad_remover.scheduler.parse_feed")
    @patch("podcast_ad_remover.scheduler.process_episode")
    def test_poll_feed_uses_custom_name(self, mock_process, mock_parse, scheduler):
        mock_parse.return_value = ("RSS Title", "Description", [
            Episode(guid="ep-1", title="Ep 1", audio_url="https://example.com/ep1.mp3"),
        ])
        mock_process.return_value = True
        feed = FeedConfig(url="https://example.com/feed.xml", name="Custom Name")
        scheduler.poll_feed(feed)
        call_kwargs = mock_process.call_args[1]
        assert call_kwargs["podcast_title"] == "Custom Name"

    @patch("podcast_ad_remover.scheduler.parse_feed")
    def test_poll_feed_continues_on_episode_error(self, mock_parse, scheduler):
        mock_parse.return_value = (
            "Test Podcast",
            "A test podcast",
            [
                Episode(guid="ep-1", title="Ep 1", audio_url="https://example.com/ep1.mp3"),
                Episode(guid="ep-2", title="Ep 2", audio_url="https://example.com/ep2.mp3"),
            ],
        )
        with patch("podcast_ad_remover.scheduler.process_episode") as mock_process:
            mock_process.side_effect = [Exception("download failed"), True]
            scheduler.poll_feed(FeedConfig(url="https://example.com/feed.xml"))
            assert mock_process.call_count == 2

    @patch("podcast_ad_remover.scheduler.parse_feed")
    def test_poll_feed_handles_feed_error(self, mock_parse, scheduler):
        mock_parse.side_effect = ValueError("Malformed XML")
        scheduler.poll_feed(FeedConfig(url="https://example.com/feed.xml"))

    @patch("podcast_ad_remover.scheduler.parse_feed")
    @patch("podcast_ad_remover.scheduler.process_episode")
    def test_poll_feed_filters_by_earliest_episode(self, mock_process, mock_parse, scheduler):
        mock_parse.return_value = (
            "Test Podcast",
            "A test podcast",
            [
                Episode(
                    guid="old", title="Old Ep",
                    audio_url="https://example.com/old.mp3",
                    pub_date="Mon, 01 Jan 2024 00:00:00 GMT",
                ),
                Episode(
                    guid="new", title="New Ep",
                    audio_url="https://example.com/new.mp3",
                    pub_date="Tue, 01 Jan 2030 00:00:00 GMT",
                ),
            ],
        )
        mock_process.return_value = True
        feed = FeedConfig(
            url="https://example.com/feed.xml",
            earliest_episode=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        scheduler.poll_feed(feed)
        assert mock_process.call_count == 1
        call_kwargs = mock_process.call_args[1]
        assert call_kwargs["episode"].guid == "new"

    @patch("podcast_ad_remover.scheduler.parse_feed")
    @patch("podcast_ad_remover.scheduler.process_episode")
    def test_poll_feed_includes_episodes_without_pub_date(
        self, mock_process, mock_parse, scheduler,
    ):
        mock_parse.return_value = (
            "Test Podcast",
            "A test podcast",
            [
                Episode(
                    guid="no-date", title="No Date Ep",
                    audio_url="https://example.com/nodate.mp3",
                    pub_date="",
                ),
            ],
        )
        mock_process.return_value = True
        feed = FeedConfig(
            url="https://example.com/feed.xml",
            earliest_episode=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        scheduler.poll_feed(feed)
        assert mock_process.call_count == 1
