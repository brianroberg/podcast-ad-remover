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
        # Gap of 6s (> 5s threshold), so segments are NOT bridged
        segments = [AdSegment(start=1.0, end=2.0), AdSegment(start=8.0, end=9.0)]
        remove_ads(sample_audio, segments, output)
        result_audio = AudioSegment.from_mp3(output)
        assert 7500 < len(result_audio) < 8500

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
        # Out of order, gap of 6s (> threshold), should still work
        segments = [AdSegment(start=8.0, end=9.0), AdSegment(start=1.0, end=2.0)]
        remove_ads(sample_audio, segments, output)
        result_audio = AudioSegment.from_mp3(output)
        assert 7500 < len(result_audio) < 8500

    def test_segment_beyond_duration_is_clamped(self, sample_audio, tmp_path):
        output = tmp_path / "output.mp3"
        segments = [AdSegment(start=8.0, end=15.0)]
        remove_ads(sample_audio, segments, output)
        result_audio = AudioSegment.from_mp3(output)
        assert 7500 < len(result_audio) < 8500

    def test_small_gap_between_ads_is_bridged(self, sample_audio, tmp_path):
        output = tmp_path / "output.mp3"
        # Two ads with a 2s gap (< 5s threshold) -> bridged into one removal
        segments = [AdSegment(start=1.0, end=2.0), AdSegment(start=4.0, end=5.0)]
        remove_ads(sample_audio, segments, output)
        result_audio = AudioSegment.from_mp3(output)
        # Bridged: removes 1.0-5.0 (4s) -> ~6s remains
        assert 5500 < len(result_audio) < 6500

    def test_large_gap_between_ads_is_preserved(self, sample_audio, tmp_path):
        output = tmp_path / "output.mp3"
        # Two ads with a 6s gap (> 5s threshold) -> NOT bridged
        segments = [AdSegment(start=1.0, end=2.0), AdSegment(start=8.0, end=9.0)]
        remove_ads(sample_audio, segments, output)
        result_audio = AudioSegment.from_mp3(output)
        # Not bridged: removes 2s total -> ~8s remains
        assert 7500 < len(result_audio) < 8500

    def test_chain_of_small_gaps_all_bridged(self, sample_audio, tmp_path):
        output = tmp_path / "output.mp3"
        # Three ads with tiny gaps: 1-2, 3-4, 5-6 (gaps are 1s each)
        segments = [
            AdSegment(start=1.0, end=2.0),
            AdSegment(start=3.0, end=4.0),
            AdSegment(start=5.0, end=6.0),
        ]
        remove_ads(sample_audio, segments, output)
        result_audio = AudioSegment.from_mp3(output)
        # Bridged into one 1.0-6.0 removal (5s) -> ~5s remains
        assert 4500 < len(result_audio) < 5500
