import httpx
import pytest
import respx

from podcast_ad_remover.audiobookshelf import AudiobookshelfClient


@pytest.fixture
def client():
    return AudiobookshelfClient(
        base_url="http://abs:13378", api_key="test-key"
    )


@pytest.fixture
def fake_episode_mp3(tmp_path):
    path = tmp_path / "episode.mp3"
    path.write_bytes(b"\xff\xfb\x90\x00" * 100)
    return path


class TestGetLibrary:
    @respx.mock
    def test_get_library_returns_folders(self, client):
        respx.get("http://abs:13378/api/libraries/lib-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "lib-1",
                    "name": "Podcasts",
                    "folders": [
                        {"id": "fold-1", "fullPath": "/podcasts"}
                    ],
                },
            )
        )
        lib = client.get_library("lib-1")
        assert lib["id"] == "lib-1"
        assert lib["folders"][0]["id"] == "fold-1"

    @respx.mock
    def test_get_library_not_found_raises(self, client):
        respx.get("http://abs:13378/api/libraries/bad-id").mock(
            return_value=httpx.Response(404)
        )
        with pytest.raises(httpx.HTTPStatusError):
            client.get_library("bad-id")


class TestFindPodcast:
    @respx.mock
    def test_find_podcast_by_title(self, client):
        respx.get("http://abs:13378/api/libraries/lib-1/items").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "li-1",
                            "media": {
                                "metadata": {
                                    "title": "My Podcast",
                                    "feedUrl": "https://example.com/feed.xml",
                                }
                            },
                        }
                    ],
                    "total": 1,
                },
            )
        )
        result = client.find_podcast("lib-1", title="My Podcast")
        assert result is not None
        assert result["id"] == "li-1"
        assert respx.calls.last.request.url.params["limit"] == "500"

    @respx.mock
    def test_find_podcast_by_feed_url(self, client):
        respx.get("http://abs:13378/api/libraries/lib-1/items").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "li-1",
                            "media": {
                                "metadata": {
                                    "title": "Some Title",
                                    "feedUrl": "https://example.com/feed.xml",
                                }
                            },
                        }
                    ],
                    "total": 1,
                },
            )
        )
        result = client.find_podcast(
            "lib-1", feed_url="https://example.com/feed.xml"
        )
        assert result is not None

    @respx.mock
    def test_find_podcast_not_found(self, client):
        respx.get("http://abs:13378/api/libraries/lib-1/items").mock(
            return_value=httpx.Response(
                200, json={"results": [], "total": 0}
            )
        )
        result = client.find_podcast("lib-1", title="Nonexistent")
        assert result is None


class TestCreatePodcast:
    @respx.mock
    def test_create_podcast(self, client):
        respx.get("http://abs:13378/api/libraries/lib-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "lib-1",
                    "folders": [
                        {"id": "fold-1", "fullPath": "/podcasts"}
                    ],
                },
            )
        )
        respx.post("http://abs:13378/api/podcasts").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "li-new",
                    "media": {
                        "metadata": {"title": "New Podcast"}
                    },
                },
            )
        )
        result = client.create_podcast(
            library_id="lib-1",
            title="New Podcast",
            feed_url="https://example.com/feed.xml",
        )
        assert result["id"] == "li-new"


class TestUploadEpisode:
    @respx.mock
    def test_upload_episode(self, client, fake_episode_mp3):
        respx.post("http://abs:13378/api/upload").mock(
            return_value=httpx.Response(200)
        )
        client.upload_episode(
            library_id="lib-1",
            folder_id="fold-1",
            podcast_title="My Podcast",
            audio_path=fake_episode_mp3,
        )
        assert respx.calls.call_count == 1


class TestScanLibraryItem:
    @respx.mock
    def test_scan_library_item(self, client):
        respx.post("http://abs:13378/api/items/li-1/scan").mock(
            return_value=httpx.Response(
                200, json={"result": "UPDATED"}
            )
        )
        client.scan_library_item("li-1")
        assert respx.calls.call_count == 1
