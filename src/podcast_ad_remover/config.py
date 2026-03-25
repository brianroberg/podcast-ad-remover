import tomllib
from pathlib import Path

from podcast_ad_remover.models import AppConfig, AudiobookshelfConfig, FeedConfig


def load_config(config_path: Path) -> AppConfig:
    """Load and validate configuration from a TOML file."""
    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    abs_section = raw.get("audiobookshelf")
    if not abs_section or not isinstance(abs_section, dict):
        raise ValueError("Config missing required section: [audiobookshelf]")
    if "url" not in abs_section:
        raise ValueError("Config [audiobookshelf] missing required field: url")
    if "library_id" not in abs_section:
        raise ValueError("Config [audiobookshelf] missing required field: library_id")

    audiobookshelf = AudiobookshelfConfig(
        url=abs_section["url"],
        library_id=abs_section["library_id"],
    )

    raw_feeds = raw.get("feeds")
    if not raw_feeds or not isinstance(raw_feeds, list) or len(raw_feeds) == 0:
        raise ValueError("Config missing required section: [[feeds]]")

    feeds = []
    for i, raw_feed in enumerate(raw_feeds):
        if "url" not in raw_feed:
            raise ValueError(f"Config feeds[{i}] missing required field: url")
        feeds.append(
            FeedConfig(
                url=raw_feed["url"],
                name=raw_feed.get("name"),
                poll_interval_hours=raw_feed.get("poll_interval_hours"),
            )
        )

    defaults = raw.get("defaults", {})
    default_poll_interval_hours = defaults.get("poll_interval_hours", 12.0)

    return AppConfig(
        audiobookshelf=audiobookshelf,
        feeds=feeds,
        default_poll_interval_hours=default_poll_interval_hours,
    )
