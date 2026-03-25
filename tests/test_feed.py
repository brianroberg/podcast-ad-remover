from unittest.mock import patch

import pytest

from podcast_ad_remover.feed import parse_feed
from podcast_ad_remover.models import Episode


def _make_feed_dict(entries=None, title="Test Podcast", author="Test Author"):
    return {
        "feed": {
            "title": title,
            "author": author,
            "subtitle": "A test podcast",
            "link": "https://example.com",
            "image": {"href": "https://example.com/cover.jpg"},
        },
        "entries": entries or [],
        "bozo": False,
    }


def _make_entry(
    guid="ep-1",
    title="Episode 1",
    audio_url="https://example.com/ep1.mp3",
    audio_type="audio/mpeg",
    summary="Episode summary",
    published="Mon, 25 Mar 2026 00:00:00 GMT",
    itunes_episode=None,
    itunes_season=None,
    itunes_episodetype="full",
):
    entry = {
        "id": guid,
        "title": title,
        "summary": summary,
        "published": published,
        "links": [
            {"rel": "enclosure", "href": audio_url, "type": audio_type},
        ],
    }
    if itunes_episode is not None:
        entry["itunes_episode"] = itunes_episode
    if itunes_season is not None:
        entry["itunes_season"] = itunes_season
    entry["itunes_episodetype"] = itunes_episodetype
    return entry


class TestParseFeed:
    @patch("podcast_ad_remover.feed.feedparser.parse")
    def test_parse_single_episode(self, mock_parse):
        mock_parse.return_value = _make_feed_dict(entries=[_make_entry()])
        podcast_title, episodes = parse_feed("https://example.com/feed.xml")
        assert podcast_title == "Test Podcast"
        assert len(episodes) == 1
        ep = episodes[0]
        assert isinstance(ep, Episode)
        assert ep.guid == "ep-1"
        assert ep.title == "Episode 1"
        assert ep.audio_url == "https://example.com/ep1.mp3"
        assert ep.description == "Episode summary"
        assert ep.pub_date == "Mon, 25 Mar 2026 00:00:00 GMT"
        assert ep.episode_type == "full"

    @patch("podcast_ad_remover.feed.feedparser.parse")
    def test_parse_multiple_episodes_returns_oldest_first(self, mock_parse):
        mock_parse.return_value = _make_feed_dict(
            entries=[
                _make_entry(
                    guid="ep-2", title="Newer", published="Tue, 26 Mar 2026 00:00:00 GMT"
                ),
                _make_entry(
                    guid="ep-1", title="Older", published="Mon, 25 Mar 2026 00:00:00 GMT"
                ),
            ],
        )
        _, episodes = parse_feed("https://example.com/feed.xml")
        assert [e.guid for e in episodes] == ["ep-1", "ep-2"]

    @patch("podcast_ad_remover.feed.feedparser.parse")
    def test_parse_episode_with_itunes_metadata(self, mock_parse):
        mock_parse.return_value = _make_feed_dict(
            entries=[
                _make_entry(itunes_episode="5", itunes_season="2", itunes_episodetype="bonus")
            ],
        )
        _, episodes = parse_feed("https://example.com/feed.xml")
        assert episodes[0].episode_number == "5"
        assert episodes[0].season_number == "2"
        assert episodes[0].episode_type == "bonus"

    @patch("podcast_ad_remover.feed.feedparser.parse")
    def test_parse_skips_non_audio_enclosures(self, mock_parse):
        entry = {
            "id": "ep-1",
            "title": "Episode 1",
            "summary": "",
            "published": "",
            "links": [
                {
                    "rel": "enclosure",
                    "href": "https://example.com/image.jpg",
                    "type": "image/jpeg",
                }
            ],
        }
        mock_parse.return_value = _make_feed_dict(entries=[entry])
        _, episodes = parse_feed("https://example.com/feed.xml")
        assert len(episodes) == 0

    @patch("podcast_ad_remover.feed.feedparser.parse")
    def test_parse_empty_feed(self, mock_parse):
        mock_parse.return_value = _make_feed_dict(entries=[])
        _, episodes = parse_feed("https://example.com/feed.xml")
        assert episodes == []

    @patch("podcast_ad_remover.feed.feedparser.parse")
    def test_parse_bozo_feed_raises(self, mock_parse):
        result = _make_feed_dict()
        result["bozo"] = True
        result["bozo_exception"] = Exception("Malformed XML")
        mock_parse.return_value = result
        with pytest.raises(ValueError, match="Failed to parse"):
            parse_feed("https://example.com/feed.xml")

    @patch("podcast_ad_remover.feed.feedparser.parse")
    def test_parse_entry_missing_guid_uses_link(self, mock_parse):
        entry = {
            "link": "https://example.com/ep1",
            "title": "Episode 1",
            "summary": "",
            "published": "",
            "links": [
                {
                    "rel": "enclosure",
                    "href": "https://example.com/ep1.mp3",
                    "type": "audio/mpeg",
                }
            ],
        }
        mock_parse.return_value = _make_feed_dict(entries=[entry])
        _, episodes = parse_feed("https://example.com/feed.xml")
        assert episodes[0].guid == "https://example.com/ep1"
