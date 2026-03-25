import pytest
from mutagen.id3 import ID3
from pydub.generators import Sine

from podcast_ad_remover.metadata import write_id3_tags
from podcast_ad_remover.models import Episode


@pytest.fixture
def mp3_file(tmp_path):
    audio = Sine(440).to_audio_segment(duration=1000)
    path = tmp_path / "episode.mp3"
    audio.export(path, format="mp3")
    return path


class TestWriteId3Tags:
    def test_writes_title(self, mp3_file):
        episode = Episode(guid="ep-1", title="My Episode", audio_url="https://example.com/ep.mp3")
        write_id3_tags(mp3_file, episode)
        tags = ID3(mp3_file)
        assert str(tags["TIT2"]) == "My Episode"

    def test_writes_description(self, mp3_file):
        episode = Episode(
            guid="ep-1", title="My Episode", audio_url="https://example.com/ep.mp3",
            description="Episode description",
        )
        write_id3_tags(mp3_file, episode)
        tags = ID3(mp3_file)
        comm_frame = tags.get("COMM::eng") or tags.get("COMM::\x00\x00\x00")
        assert comm_frame is not None
        assert "Episode description" in str(comm_frame)

    def test_writes_episode_number(self, mp3_file):
        episode = Episode(
            guid="ep-1", title="My Episode", audio_url="https://example.com/ep.mp3",
            episode_number="42",
        )
        write_id3_tags(mp3_file, episode)
        tags = ID3(mp3_file)
        assert str(tags["TRCK"]) == "42"

    def test_writes_pub_date(self, mp3_file):
        episode = Episode(
            guid="ep-1", title="My Episode", audio_url="https://example.com/ep.mp3",
            pub_date="Mon, 25 Mar 2026 00:00:00 GMT",
        )
        write_id3_tags(mp3_file, episode)
        tags = ID3(mp3_file)
        assert "2026" in str(tags["TDRC"])
