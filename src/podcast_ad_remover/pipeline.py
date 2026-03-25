import logging
from pathlib import Path

from google import genai

from podcast_ad_remover.ad_detector import detect_ads
from podcast_ad_remover.audio_processor import remove_ads
from podcast_ad_remover.audiobookshelf import AudiobookshelfClient
from podcast_ad_remover.downloader import download_episode
from podcast_ad_remover.metadata import write_id3_tags
from podcast_ad_remover.models import Episode
from podcast_ad_remover.state import StateManager

logger = logging.getLogger(__name__)


def process_episode(
    episode: Episode,
    feed_url: str,
    podcast_title: str,
    library_id: str,
    gemini_api_key: str,
    abs_client: AudiobookshelfClient,
    state: StateManager,
    work_dir: Path,
    gemini_client: genai.Client | None = None,
    podcast_description: str | None = None,
) -> bool:
    """Process a single podcast episode. Returns True if processed, False if skipped."""
    if state.is_processed(feed_url, episode.guid):
        logger.debug("Skipping already-processed episode: %s", episode.title)
        return False

    logger.info("Processing episode: %s", episode.title)

    # Download
    download_dir = work_dir / "downloads"
    download_dir.mkdir(exist_ok=True)
    audio_path = download_episode(episode.audio_url, download_dir)

    # Detect ads (None = detection failed, [] = no ads found, [...] = ads found)
    segments = detect_ads(
        audio_path,
        api_key=gemini_api_key,
        client=gemini_client,
        podcast_title=podcast_title,
        podcast_description=podcast_description,
    )

    # Process audio
    if segments is None:
        # Detection failed — upload original as fallback
        upload_path = audio_path
        status = "fallback"
        ad_count = 0
    elif segments:
        # Ads found — cut them out
        output_dir = work_dir / "processed"
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / audio_path.name
        upload_path = remove_ads(audio_path, segments, output_path)
        status = "success"
        ad_count = len(segments)
    else:
        # No ads found (clean episode) — upload original
        upload_path = audio_path
        status = "success"
        ad_count = 0

    # Write ID3 metadata
    write_id3_tags(upload_path, episode)

    # Ensure podcast exists in Audiobookshelf
    podcast_item = abs_client.find_podcast(library_id, title=podcast_title, feed_url=feed_url)
    if podcast_item is None:
        podcast_item = abs_client.create_podcast(
            library_id=library_id, title=podcast_title, feed_url=feed_url,
        )

    library_item_id = podcast_item["id"]

    # Get folder ID
    library = abs_client.get_library(library_id)
    folder_id = library["folders"][0]["id"]

    # Upload
    abs_client.upload_episode(
        library_id=library_id, folder_id=folder_id,
        podcast_title=podcast_title, audio_path=upload_path,
    )

    # Trigger scan to detect the new episode (best-effort)
    try:
        abs_client.scan_library_item(library_item_id)
    except Exception:
        logger.warning("Failed to trigger scan for library item %s", library_item_id)

    # Mark as processed (only after successful upload)
    state.mark_processed(
        feed_url, episode.guid, ad_segments_found=ad_count, status=status,
    )

    logger.info(
        "Episode '%s' processed: %d ad segments removed (status: %s)",
        episode.title, ad_count, status,
    )
    return True
