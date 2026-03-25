from unittest.mock import patch

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
        mock_parse.return_value = ("RSS Title", [
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
