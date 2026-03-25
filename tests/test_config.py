import pytest

from podcast_ad_remover.config import load_config
from podcast_ad_remover.models import AppConfig


class TestLoadConfig:
    def test_load_valid_config(self, sample_config_toml):
        config = load_config(sample_config_toml)
        assert isinstance(config, AppConfig)
        assert config.audiobookshelf.url == "http://localhost:13378"
        assert config.audiobookshelf.library_id == "lib-123"
        assert config.default_poll_interval_hours == 6.0
        assert len(config.feeds) == 2
        assert config.feeds[0].url == "https://example.com/feed.xml"
        assert config.feeds[0].name is None
        assert config.feeds[1].name == "Custom Name"
        assert config.feeds[1].poll_interval_hours == 1

    def test_load_config_default_interval(self, tmp_path):
        config_content = """\
[audiobookshelf]
url = "http://localhost:13378"
library_id = "lib-123"

[[feeds]]
url = "https://example.com/feed.xml"
"""
        config_path = tmp_path / "config.toml"
        config_path.write_text(config_content)
        config = load_config(config_path)
        assert config.default_poll_interval_hours == 12.0

    def test_load_config_missing_audiobookshelf(self, tmp_path):
        config_path = tmp_path / "config.toml"
        config_path.write_text('[[feeds]]\nurl = "https://example.com/feed.xml"\n')
        with pytest.raises(ValueError, match="audiobookshelf"):
            load_config(config_path)

    def test_load_config_missing_feeds(self, tmp_path):
        config_path = tmp_path / "config.toml"
        config_path.write_text('[audiobookshelf]\nurl = "http://localhost"\nlibrary_id = "lib-1"\n')
        with pytest.raises(ValueError, match="feeds"):
            load_config(config_path)

    def test_load_config_empty_feeds(self, tmp_path):
        config_content = """\
[audiobookshelf]
url = "http://localhost"
library_id = "lib-1"
"""
        config_path = tmp_path / "config.toml"
        config_path.write_text(config_content)
        with pytest.raises(ValueError, match="feeds"):
            load_config(config_path)

    def test_load_config_missing_feed_url(self, tmp_path):
        config_content = """\
[audiobookshelf]
url = "http://localhost"
library_id = "lib-1"

[[feeds]]
name = "No URL"
"""
        config_path = tmp_path / "config.toml"
        config_path.write_text(config_content)
        with pytest.raises(ValueError, match="url"):
            load_config(config_path)

    def test_load_config_missing_audiobookshelf_url(self, tmp_path):
        config_content = """\
[audiobookshelf]
library_id = "lib-1"

[[feeds]]
url = "https://example.com/feed.xml"
"""
        config_path = tmp_path / "config.toml"
        config_path.write_text(config_content)
        with pytest.raises(ValueError, match="url"):
            load_config(config_path)

    def test_load_config_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.toml")
