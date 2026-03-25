import logging
import re
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


def _sanitize_filename(name: str) -> str:
    """Remove characters unsafe for filesystem paths."""
    sanitized = re.sub(r'[<>:"/\\|?*]', "", name)
    sanitized = sanitized.replace("..", "")
    return sanitized.strip(". ") or "Untitled Podcast"


class AudiobookshelfClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )

    def get_library(self, library_id: str) -> dict:
        response = self._client.get(f"{self.base_url}/api/libraries/{library_id}")
        response.raise_for_status()
        return response.json()

    def find_podcast(
        self,
        library_id: str,
        title: str | None = None,
        feed_url: str | None = None,
    ) -> dict | None:
        """Find an existing podcast by title or feed URL, paginating through all results."""
        page = 0
        page_size = 100
        while True:
            response = self._client.get(
                f"{self.base_url}/api/libraries/{library_id}/items",
                params={"limit": page_size, "page": page},
            )
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            for item in results:
                metadata = item.get("media", {}).get("metadata", {})
                if feed_url and metadata.get("feedUrl") == feed_url:
                    return item
                if title and metadata.get("title") == title:
                    return item
            if len(results) < page_size:
                break
            page += 1
        return None

    def create_podcast(
        self,
        library_id: str,
        title: str,
        feed_url: str | None = None,
        author: str | None = None,
        description: str | None = None,
        image_url: str | None = None,
    ) -> dict:
        library = self.get_library(library_id)
        folder = library["folders"][0]
        folder_id = folder["id"]
        folder_path = folder["fullPath"]
        podcast_path = f"{folder_path}/{_sanitize_filename(title)}"
        payload = {
            "libraryId": library_id,
            "folderId": folder_id,
            "path": podcast_path,
            "media": {
                "metadata": {
                    "title": title,
                    "feedUrl": feed_url,
                    "author": author,
                    "description": description,
                    "imageUrl": image_url,
                }
            },
        }
        logger.info("Creating podcast '%s' in Audiobookshelf", title)
        response = self._client.post(f"{self.base_url}/api/podcasts", json=payload)
        response.raise_for_status()
        return response.json()

    def upload_episode(
        self,
        library_id: str,
        folder_id: str,
        podcast_title: str,
        audio_path: Path,
    ):
        logger.info("Uploading %s to podcast '%s'", audio_path.name, podcast_title)
        with open(audio_path, "rb") as f:
            response = self._client.post(
                f"{self.base_url}/api/upload",
                data={
                    "title": podcast_title,
                    "library": library_id,
                    "folder": folder_id,
                },
                files={"0": (audio_path.name, f, "audio/mpeg")},
                timeout=300.0,
            )
        response.raise_for_status()

    def scan_library_item(self, library_item_id: str):
        logger.info("Scanning library item %s", library_item_id)
        response = self._client.post(
            f"{self.base_url}/api/items/{library_item_id}/scan"
        )
        response.raise_for_status()

    def close(self):
        self._client.close()
