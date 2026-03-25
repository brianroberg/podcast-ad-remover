from podcast_ad_remover.models import (
    AdSegment,
    AppConfig,
    AudiobookshelfConfig,
    Episode,
    FeedConfig,
)


class TestFeedConfig:
    def test_create_minimal(self):
        feed = FeedConfig(url="https://example.com/feed.xml")
        assert feed.url == "https://example.com/feed.xml"
        assert feed.name is None
        assert feed.poll_interval_hours is None

    def test_create_full(self):
        feed = FeedConfig(
            url="https://example.com/feed.xml",
            name="My Podcast",
            poll_interval_hours=6,
        )
        assert feed.name == "My Podcast"
        assert feed.poll_interval_hours == 6


class TestAudiobookshelfConfig:
    def test_create(self):
        config = AudiobookshelfConfig(url="http://localhost:13378", library_id="lib-123")
        assert config.url == "http://localhost:13378"
        assert config.library_id == "lib-123"


class TestAppConfig:
    def test_create_with_defaults(self):
        config = AppConfig(
            audiobookshelf=AudiobookshelfConfig(url="http://localhost:13378", library_id="lib-123"),
            feeds=[FeedConfig(url="https://example.com/feed.xml")],
        )
        assert config.default_poll_interval_hours == 12.0

    def test_create_with_custom_interval(self):
        config = AppConfig(
            audiobookshelf=AudiobookshelfConfig(url="http://localhost:13378", library_id="lib-123"),
            feeds=[FeedConfig(url="https://example.com/feed.xml")],
            default_poll_interval_hours=6.0,
        )
        assert config.default_poll_interval_hours == 6.0


class TestEpisode:
    def test_create_minimal(self):
        ep = Episode(guid="ep-1", title="Episode 1", audio_url="https://example.com/ep1.mp3")
        assert ep.guid == "ep-1"
        assert ep.title == "Episode 1"
        assert ep.audio_url == "https://example.com/ep1.mp3"
        assert ep.description == ""
        assert ep.pub_date == ""
        assert ep.episode_number is None
        assert ep.season_number is None
        assert ep.episode_type == "full"

    def test_create_full(self):
        ep = Episode(
            guid="ep-1",
            title="Episode 1",
            audio_url="https://example.com/ep1.mp3",
            description="A great episode",
            pub_date="Mon, 25 Mar 2026 00:00:00 GMT",
            episode_number="5",
            season_number="2",
            episode_type="bonus",
        )
        assert ep.description == "A great episode"
        assert ep.episode_number == "5"
        assert ep.season_number == "2"
        assert ep.episode_type == "bonus"


class TestAdSegment:
    def test_create(self):
        seg = AdSegment(start=45.0, end=120.5)
        assert seg.start == 45.0
        assert seg.end == 120.5
