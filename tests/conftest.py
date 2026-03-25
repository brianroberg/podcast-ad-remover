import pytest


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary directory for test files."""
    return tmp_path


@pytest.fixture
def sample_config_toml(tmp_path):
    """Write a valid config.toml to a temp file and return its path."""
    config_content = """\
[audiobookshelf]
url = "http://localhost:13378"
library_id = "lib-123"

[defaults]
poll_interval_hours = 6

[[feeds]]
url = "https://example.com/feed.xml"

[[feeds]]
url = "https://example.com/other.xml"
name = "Custom Name"
poll_interval_hours = 1
"""
    config_path = tmp_path / "config.toml"
    config_path.write_text(config_content)
    return config_path
