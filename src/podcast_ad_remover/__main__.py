import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from podcast_ad_remover.config import load_config
from podcast_ad_remover.scheduler import Scheduler


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )
    logger = logging.getLogger("podcast_ad_remover")

    # Load .env
    load_dotenv()

    # Load config
    config_path = Path(os.getenv("CONFIG_PATH", "config.toml"))
    if not config_path.exists():
        logger.error("Config file not found: %s", config_path)
        sys.exit(1)

    try:
        config = load_config(config_path)
    except (ValueError, FileNotFoundError) as e:
        logger.error("Invalid configuration: %s", e)
        sys.exit(1)

    # Read API keys
    abs_api_key = os.getenv("AUDIOBOOKSHELF_API_KEY")
    if not abs_api_key:
        logger.error("AUDIOBOOKSHELF_API_KEY not set in environment")
        sys.exit(1)

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        logger.error("GEMINI_API_KEY not set in environment")
        sys.exit(1)

    data_dir = Path(os.getenv("DATA_DIR", "data"))

    logger.info("Starting Podcast Ad Remover")
    logger.info("Audiobookshelf: %s", config.audiobookshelf.url)
    logger.info("Feeds: %d configured", len(config.feeds))

    scheduler = Scheduler(
        config=config,
        abs_api_key=abs_api_key,
        gemini_api_key=gemini_api_key,
        data_dir=data_dir,
    )

    asyncio.run(scheduler.run())


if __name__ == "__main__":
    main()
