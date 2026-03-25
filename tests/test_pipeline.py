from unittest.mock import MagicMock, patch

import pytest

from podcast_ad_remover.models import AdSegment, Episode
from podcast_ad_remover.pipeline import _episode_filename, process_episode

PODCAST_ITEM = {
    "id": "li-1",
    "media": {"metadata": {"title": "Podcast"}},
}
LIBRARY_DATA = {
    "folders": [{"id": "fold-1", "fullPath": "/podcasts"}],
}


@pytest.fixture
def episode():
    return Episode(
        guid="ep-1",
        title="Episode 1",
        audio_url="https://example.com/ep1.mp3",
        description="A great episode",
        pub_date="Mon, 25 Mar 2026 00:00:00 GMT",
        episode_number="5",
        season_number="2",
        episode_type="full",
    )


@pytest.fixture
def fake_audio(tmp_path):
    path = tmp_path / "ep1.mp3"
    path.write_bytes(b"\xff\xfb\x90\x00" * 100)
    return path


def _make_abs_client(podcast_item=None):
    client = MagicMock()
    client.find_podcast.return_value = (
        podcast_item if podcast_item is not None else PODCAST_ITEM
    )
    client.get_library.return_value = LIBRARY_DATA
    return client


def _make_state(is_processed=False):
    state = MagicMock()
    state.is_processed.return_value = is_processed
    return state


def _call_process(episode, tmp_path, abs_client, state):
    return process_episode(
        episode=episode,
        feed_url="https://example.com/feed.xml",
        podcast_title="Podcast",
        library_id="lib-1",
        gemini_api_key="gem-key",
        abs_client=abs_client,
        state=state,
        work_dir=tmp_path,
    )


class TestProcessEpisode:
    @patch("podcast_ad_remover.pipeline.write_id3_tags")
    @patch("podcast_ad_remover.pipeline.remove_ads")
    @patch("podcast_ad_remover.pipeline.detect_ads")
    @patch("podcast_ad_remover.pipeline.download_episode")
    def test_success_with_ads(
        self, mock_download, mock_detect, mock_remove,
        mock_tags, episode, fake_audio, tmp_path,
    ):
        mock_download.return_value = fake_audio
        mock_detect.return_value = [AdSegment(start=10.0, end=20.0)]
        processed_path = tmp_path / "processed.mp3"
        processed_path.write_bytes(b"processed")
        mock_remove.return_value = processed_path

        abs_client = _make_abs_client()
        state = _make_state()

        result = _call_process(episode, tmp_path, abs_client, state)

        assert result is True
        mock_download.assert_called_once()
        mock_detect.assert_called_once()
        mock_remove.assert_called_once()
        abs_client.upload_episode.assert_called_once()
        abs_client.scan_library_item.assert_called_once_with("li-1")
        state.mark_processed.assert_called_once_with(
            "https://example.com/feed.xml", "ep-1",
            ad_segments_found=1, status="success",
        )

    @patch("podcast_ad_remover.pipeline.write_id3_tags")
    @patch("podcast_ad_remover.pipeline.detect_ads")
    @patch("podcast_ad_remover.pipeline.download_episode")
    def test_fallback_on_detection_failure(
        self, mock_download, mock_detect, mock_tags,
        episode, fake_audio, tmp_path,
    ):
        mock_download.return_value = fake_audio
        mock_detect.return_value = None  # Detection failed

        abs_client = _make_abs_client()
        state = _make_state()

        result = _call_process(episode, tmp_path, abs_client, state)

        assert result is True
        abs_client.upload_episode.assert_called_once()
        state.mark_processed.assert_called_once_with(
            "https://example.com/feed.xml", "ep-1",
            ad_segments_found=0, status="fallback",
        )

    @patch("podcast_ad_remover.pipeline.write_id3_tags")
    @patch("podcast_ad_remover.pipeline.detect_ads")
    @patch("podcast_ad_remover.pipeline.download_episode")
    def test_no_ads_found_uploads_original(
        self, mock_download, mock_detect, mock_tags,
        episode, fake_audio, tmp_path,
    ):
        mock_download.return_value = fake_audio
        mock_detect.return_value = []  # No ads (detection succeeded)

        abs_client = _make_abs_client()
        state = _make_state()

        result = _call_process(episode, tmp_path, abs_client, state)

        assert result is True
        abs_client.upload_episode.assert_called_once()
        state.mark_processed.assert_called_once_with(
            "https://example.com/feed.xml", "ep-1",
            ad_segments_found=0, status="success",
        )

    @patch("podcast_ad_remover.pipeline.download_episode")
    def test_skips_already_processed(
        self, mock_download, episode, tmp_path,
    ):
        abs_client = _make_abs_client()
        state = _make_state(is_processed=True)

        result = _call_process(episode, tmp_path, abs_client, state)

        assert result is False
        mock_download.assert_not_called()

    @patch("podcast_ad_remover.pipeline.write_id3_tags")
    @patch("podcast_ad_remover.pipeline.detect_ads")
    @patch("podcast_ad_remover.pipeline.download_episode")
    def test_upload_failure_does_not_mark_processed(
        self, mock_download, mock_detect, mock_tags,
        episode, fake_audio, tmp_path,
    ):
        mock_download.return_value = fake_audio
        mock_detect.return_value = None

        abs_client = _make_abs_client()
        abs_client.upload_episode.side_effect = Exception(
            "Upload failed"
        )
        state = _make_state()

        with pytest.raises(Exception, match="Upload failed"):
            _call_process(episode, tmp_path, abs_client, state)

        state.mark_processed.assert_not_called()

    @patch("podcast_ad_remover.pipeline.write_id3_tags")
    @patch("podcast_ad_remover.pipeline.detect_ads")
    @patch("podcast_ad_remover.pipeline.download_episode")
    def test_creates_podcast_if_not_found(
        self, mock_download, mock_detect, mock_tags,
        episode, fake_audio, tmp_path,
    ):
        mock_download.return_value = fake_audio
        mock_detect.return_value = []
        abs_client = MagicMock()
        abs_client.find_podcast.return_value = None
        abs_client.create_podcast.return_value = {"id": "li-new"}
        abs_client.get_library.return_value = LIBRARY_DATA

        state = _make_state()

        _call_process(episode, tmp_path, abs_client, state)

        abs_client.create_podcast.assert_called_once_with(
            library_id="lib-1",
            title="Podcast",
            feed_url="https://example.com/feed.xml",
        )

    @patch("podcast_ad_remover.pipeline.write_id3_tags")
    @patch("podcast_ad_remover.pipeline.detect_ads")
    @patch("podcast_ad_remover.pipeline.download_episode")
    def test_scan_failure_does_not_prevent_marking_processed(
        self, mock_download, mock_detect, mock_tags,
        episode, fake_audio, tmp_path,
    ):
        mock_download.return_value = fake_audio
        mock_detect.return_value = None

        abs_client = _make_abs_client()
        abs_client.scan_library_item.side_effect = Exception(
            "Scan failed"
        )
        state = _make_state()

        result = _call_process(episode, tmp_path, abs_client, state)

        assert result is True
        state.mark_processed.assert_called_once()


class TestEpisodeFilename:
    def test_basic_title(self):
        ep = Episode(guid="1", title="My Great Episode", audio_url="http://x/a.mp3")
        assert _episode_filename(ep) == "my-great-episode.mp3"

    def test_with_episode_number(self):
        ep = Episode(
            guid="1", title="Season Opener", audio_url="http://x/a.mp3",
            episode_number="42",
        )
        assert _episode_filename(ep) == "42-season-opener.mp3"

    def test_strips_special_characters(self):
        ep = Episode(
            guid="1", title="What's Up? #100 — The Big Game!",
            audio_url="http://x/a.mp3",
        )
        assert _episode_filename(ep) == "whats-up-100-the-big-game.mp3"

    def test_collapses_multiple_spaces(self):
        ep = Episode(guid="1", title="Too   Many   Spaces", audio_url="http://x/a.mp3")
        assert _episode_filename(ep) == "too-many-spaces.mp3"

    def test_empty_title_fallback(self):
        ep = Episode(guid="1", title="!!!", audio_url="http://x/a.mp3")
        assert _episode_filename(ep) == "episode.mp3"

    def test_pipe_and_numbers(self):
        ep = Episode(
            guid="1",
            title="2026 New York Mets Season Preview w/ Daniel Murphy | 542",
            audio_url="http://x/a.mp3",
            episode_number="542",
        )
        assert _episode_filename(ep) == "542-2026-new-york-mets-season-preview-w-daniel-murphy-542.mp3"
