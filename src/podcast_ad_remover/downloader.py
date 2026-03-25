import logging
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

logger = logging.getLogger(__name__)


def download_episode(audio_url: str, download_dir: Path) -> Path:
    parsed = urlparse(audio_url)
    filename = unquote(Path(parsed.path).name) or "episode.mp3"
    dest = download_dir / filename
    logger.info("Downloading %s to %s", audio_url, dest)
    timeout = httpx.Timeout(10.0, read=300.0)
    with httpx.stream("GET", audio_url, follow_redirects=True, timeout=timeout) as response:
        response.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in response.iter_bytes(chunk_size=8192):
                f.write(chunk)
    logger.info("Downloaded %s (%d bytes)", filename, dest.stat().st_size)
    return dest
