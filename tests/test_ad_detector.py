from unittest.mock import MagicMock, patch

import pytest

from podcast_ad_remover.ad_detector import detect_ads
from podcast_ad_remover.models import AdSegment


@pytest.fixture
def fake_audio(tmp_path):
    audio_path = tmp_path / "episode.mp3"
    audio_path.write_bytes(b"\xff\xfb\x90\x00" * 100)
    return audio_path


class TestDetectAds:
    @patch("podcast_ad_remover.ad_detector.genai")
    def test_detect_ads_success(self, mock_genai, fake_audio):
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_file = MagicMock()
        mock_client.files.upload.return_value = mock_file
        mock_response = MagicMock()
        mock_response.text = '[{"start": 45.0, "end": 120.5}, {"start": 900.0, "end": 960.0}]'
        mock_client.models.generate_content.return_value = mock_response
        segments = detect_ads(fake_audio, api_key="test-key")
        assert len(segments) == 2
        assert segments[0] == AdSegment(start=45.0, end=120.5)
        assert segments[1] == AdSegment(start=900.0, end=960.0)

    @patch("podcast_ad_remover.ad_detector.genai")
    def test_detect_ads_no_ads_found(self, mock_genai, fake_audio):
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.files.upload.return_value = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "[]"
        mock_client.models.generate_content.return_value = mock_response
        segments = detect_ads(fake_audio, api_key="test-key")
        assert segments == []

    @patch("podcast_ad_remover.ad_detector.genai")
    def test_detect_ads_invalid_json_returns_none(self, mock_genai, fake_audio):
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.files.upload.return_value = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "not valid json at all"
        mock_client.models.generate_content.return_value = mock_response
        segments = detect_ads(fake_audio, api_key="test-key")
        assert segments is None

    @patch("podcast_ad_remover.ad_detector.genai")
    def test_detect_ads_malformed_segments_returns_none(self, mock_genai, fake_audio):
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.files.upload.return_value = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '[{"begin": 10, "finish": 20}]'
        mock_client.models.generate_content.return_value = mock_response
        segments = detect_ads(fake_audio, api_key="test-key")
        assert segments is None

    @patch("podcast_ad_remover.ad_detector.genai")
    def test_detect_ads_api_error_returns_none(self, mock_genai, fake_audio):
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.files.upload.side_effect = Exception("API rate limit")
        segments = detect_ads(fake_audio, api_key="test-key")
        assert segments is None

    @patch("podcast_ad_remover.ad_detector.genai")
    def test_detect_ads_cleans_up_uploaded_file(self, mock_genai, fake_audio):
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_file = MagicMock()
        mock_file.name = "files/abc123"
        mock_client.files.upload.return_value = mock_file
        mock_response = MagicMock()
        mock_response.text = "[]"
        mock_client.models.generate_content.return_value = mock_response
        detect_ads(fake_audio, api_key="test-key")
        mock_client.files.delete.assert_called_once_with(name="files/abc123")
