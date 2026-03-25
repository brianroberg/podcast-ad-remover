import httpx
import pytest
import respx

from podcast_ad_remover.downloader import download_episode


class TestDownloadEpisode:
    @respx.mock
    def test_download_success(self, tmp_path):
        audio_content = b"\xff\xfb\x90\x00" * 100
        respx.get("https://example.com/ep1.mp3").mock(
            return_value=httpx.Response(200, content=audio_content)
        )
        path = download_episode("https://example.com/ep1.mp3", tmp_path)
        assert path.exists()
        assert path.read_bytes() == audio_content
        assert path.suffix == ".mp3"

    @respx.mock
    def test_download_preserves_filename(self, tmp_path):
        respx.get("https://example.com/my-episode.mp3").mock(
            return_value=httpx.Response(200, content=b"audio")
        )
        path = download_episode("https://example.com/my-episode.mp3", tmp_path)
        assert path.name == "my-episode.mp3"

    @respx.mock
    def test_download_http_error_raises(self, tmp_path):
        respx.get("https://example.com/ep1.mp3").mock(
            return_value=httpx.Response(404)
        )
        with pytest.raises(httpx.HTTPStatusError):
            download_episode("https://example.com/ep1.mp3", tmp_path)

    @respx.mock
    def test_download_url_with_query_params(self, tmp_path):
        respx.get("https://example.com/ep1.mp3").mock(
            return_value=httpx.Response(200, content=b"audio")
        )
        path = download_episode("https://example.com/ep1.mp3?token=abc", tmp_path)
        assert path.name == "ep1.mp3"
