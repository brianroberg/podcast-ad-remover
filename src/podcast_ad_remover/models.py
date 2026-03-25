from dataclasses import dataclass
from datetime import datetime


@dataclass
class FeedConfig:
    url: str
    name: str | None = None
    poll_interval_hours: float | None = None
    earliest_episode: datetime | None = None


@dataclass
class AudiobookshelfConfig:
    url: str
    library_id: str


@dataclass
class AppConfig:
    audiobookshelf: AudiobookshelfConfig
    feeds: list[FeedConfig]
    default_poll_interval_hours: float = 12.0


@dataclass
class Episode:
    guid: str
    title: str
    audio_url: str
    description: str = ""
    pub_date: str = ""
    episode_number: str | None = None
    season_number: str | None = None
    episode_type: str = "full"


@dataclass
class AdSegment:
    start: float
    end: float
