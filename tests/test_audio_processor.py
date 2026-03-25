import pytest
from pydub import AudioSegment
from pydub.generators import Sine

from podcast_ad_remover.audio_processor import remove_ads
from podcast_ad_remover.models import AdSegment


@pytest.fixture
def sample_audio(tmp_path):
    audio = Sine(440).to_audio_segment(duration=10000)
    path = tmp_path / "input.mp3"
    audio.export(path, format="mp3")
    return path


class TestRemoveAds:
    def test_no_segments_returns_copy(self, sample_audio, tmp_path):
        output = tmp_path / "output.mp3"
        result = remove_ads(sample_audio, [], output)
        assert result == output
        assert output.exists()
        result_audio = AudioSegment.from_mp3(output)
        original_audio = AudioSegment.from_mp3(sample_audio)
        assert abs(len(result_audio) - len(original_audio)) < 100

    def test_remove_single_segment(self, sample_audio, tmp_path):
        output = tmp_path / "output.mp3"
        segments = [AdSegment(start=2.0, end=4.0)]
        remove_ads(sample_audio, segments, output)
        result_audio = AudioSegment.from_mp3(output)
        assert 7500 < len(result_audio) < 8500

    def test_remove_multiple_segments(self, sample_audio, tmp_path):
        output = tmp_path / "output.mp3"
        segments = [AdSegment(start=1.0, end=2.0), AdSegment(start=5.0, end=7.0)]
        remove_ads(sample_audio, segments, output)
        result_audio = AudioSegment.from_mp3(output)
        assert 6500 < len(result_audio) < 7500

    def test_remove_segment_at_start(self, sample_audio, tmp_path):
        output = tmp_path / "output.mp3"
        segments = [AdSegment(start=0.0, end=3.0)]
        remove_ads(sample_audio, segments, output)
        result_audio = AudioSegment.from_mp3(output)
        assert 6500 < len(result_audio) < 7500

    def test_remove_segment_at_end(self, sample_audio, tmp_path):
        output = tmp_path / "output.mp3"
        segments = [AdSegment(start=8.0, end=10.0)]
        remove_ads(sample_audio, segments, output)
        result_audio = AudioSegment.from_mp3(output)
        assert 7500 < len(result_audio) < 8500

    def test_overlapping_segments_are_merged(self, sample_audio, tmp_path):
        output = tmp_path / "output.mp3"
        segments = [AdSegment(start=2.0, end=5.0), AdSegment(start=4.0, end=7.0)]
        remove_ads(sample_audio, segments, output)
        result_audio = AudioSegment.from_mp3(output)
        assert 4500 < len(result_audio) < 5500

    def test_unsorted_segments_are_handled(self, sample_audio, tmp_path):
        output = tmp_path / "output.mp3"
        segments = [AdSegment(start=5.0, end=7.0), AdSegment(start=1.0, end=2.0)]
        remove_ads(sample_audio, segments, output)
        result_audio = AudioSegment.from_mp3(output)
        assert 6500 < len(result_audio) < 7500

    def test_segment_beyond_duration_is_clamped(self, sample_audio, tmp_path):
        output = tmp_path / "output.mp3"
        segments = [AdSegment(start=8.0, end=15.0)]
        remove_ads(sample_audio, segments, output)
        result_audio = AudioSegment.from_mp3(output)
        assert 7500 < len(result_audio) < 8500
