import logging
from email.utils import parsedate_to_datetime

import feedparser

from podcast_ad_remover.models import Episode

logger = logging.getLogger(__name__)


def parse_feed(feed_url: str) -> tuple[str, list[Episode]]:
    result = feedparser.parse(feed_url)
    if result.get("bozo") and result.get("bozo_exception"):
        raise ValueError(f"Failed to parse feed {feed_url}: {result['bozo_exception']}")

    podcast_title = result.get("feed", {}).get("title", "Unknown Podcast")
    episodes = []
    for entry in result.get("entries", []):
        audio_url = _extract_audio_url(entry)
        if audio_url is None:
            logger.debug("Skipping entry %s — no audio enclosure", entry.get("title", "unknown"))
            continue
        guid = entry.get("id") or entry.get("link") or audio_url
        episodes.append(
            Episode(
                guid=guid,
                title=entry.get("title", ""),
                audio_url=audio_url,
                description=entry.get("summary", ""),
                pub_date=entry.get("published", ""),
                episode_number=entry.get("itunes_episode"),
                season_number=entry.get("itunes_season"),
                episode_type=entry.get("itunes_episodetype", "full"),
            )
        )
    episodes.sort(key=_episode_sort_key)
    return podcast_title, episodes


def _extract_audio_url(entry: dict) -> str | None:
    for link in entry.get("links", []):
        if link.get("rel") == "enclosure" and link.get("type", "").startswith("audio/"):
            return link["href"]
    return None


def _episode_sort_key(episode: Episode):
    if not episode.pub_date:
        return 0
    try:
        return parsedate_to_datetime(episode.pub_date).timestamp()
    except Exception:
        return 0
