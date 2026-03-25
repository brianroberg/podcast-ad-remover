import asyncio
import logging
import tempfile
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from google import genai

from podcast_ad_remover.audiobookshelf import AudiobookshelfClient
from podcast_ad_remover.feed import parse_feed
from podcast_ad_remover.models import AppConfig, Episode, FeedConfig
from podcast_ad_remover.pipeline import process_episode
from podcast_ad_remover.state import StateManager

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(
        self,
        config: AppConfig,
        abs_api_key: str,
        gemini_api_key: str,
        data_dir: str | Path,
    ):
        self.config = config
        self.gemini_api_key = gemini_api_key
        self.gemini_client = genai.Client(api_key=gemini_api_key)
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state = StateManager(self.data_dir / "state.db")
        self.abs_client = AudiobookshelfClient(
            base_url=config.audiobookshelf.url, api_key=abs_api_key,
        )

    @staticmethod
    def _is_before_cutoff(episode: Episode, cutoff: datetime) -> bool:
        """Return True if the episode's pub_date is before the cutoff."""
        if not episode.pub_date:
            return False
        try:
            pub_dt = parsedate_to_datetime(episode.pub_date)
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            return pub_dt < cutoff
        except Exception:
            return False

    def _effective_interval_seconds(self, feed: FeedConfig) -> float:
        hours = feed.poll_interval_hours or self.config.default_poll_interval_hours
        return hours * 3600

    def poll_feed(self, feed: FeedConfig):
        try:
            podcast_title, episodes = parse_feed(feed.url)
        except Exception:
            logger.exception("Failed to fetch feed: %s", feed.url)
            return

        display_name = feed.name or podcast_title

        if feed.earliest_episode:
            before = len(episodes)
            cutoff = feed.earliest_episode
            episodes = [ep for ep in episodes if not self._is_before_cutoff(ep, cutoff)]
            skipped = before - len(episodes)
            if skipped:
                logger.info(
                    "Polled '%s': %d episodes found, %d skipped (before %s)",
                    display_name, before, skipped, feed.earliest_episode.date(),
                )
            else:
                logger.info("Polled '%s': %d episodes found", display_name, len(episodes))
        else:
            logger.info("Polled '%s': %d episodes found", display_name, len(episodes))

        for episode in episodes:
            try:
                with tempfile.TemporaryDirectory() as work_dir:
                    process_episode(
                        episode=episode, feed_url=feed.url, podcast_title=display_name,
                        library_id=self.config.audiobookshelf.library_id,
                        gemini_api_key=self.gemini_api_key,
                        gemini_client=self.gemini_client,
                        abs_client=self.abs_client, state=self.state, work_dir=Path(work_dir),
                    )
            except Exception:
                logger.exception(
                    "Failed to process episode '%s' from '%s'",
                    episode.title, display_name,
                )

    async def run(self):
        logger.info("Starting scheduler with %d feeds", len(self.config.feeds))
        tasks = [self._feed_loop(feed) for feed in self.config.feeds]
        try:
            await asyncio.gather(*tasks)
        finally:
            self.abs_client.close()

    async def _feed_loop(self, feed: FeedConfig):
        interval = self._effective_interval_seconds(feed)
        name = feed.name or feed.url
        logger.info("Starting poll loop for '%s' (every %.1f hours)", name, interval / 3600)
        while True:
            logger.info("Polling feed: %s", name)
            await asyncio.to_thread(self.poll_feed, feed)
            logger.info("Next poll for '%s' in %.1f hours", name, interval / 3600)
            await asyncio.sleep(interval)
