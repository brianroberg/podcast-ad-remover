# Podcast Ad Remover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python application that polls podcast RSS feeds, removes ads using Gemini 2.5 Flash, and uploads cleaned episodes to Audiobookshelf.

**Architecture:** A long-lived Python process runs in Docker alongside Audiobookshelf. It schedules per-feed polling loops using asyncio. Each poll fetches the RSS feed, downloads new episodes, sends audio to Gemini for ad timestamp detection, cuts out ad segments with pydub, and uploads cleaned episodes via the Audiobookshelf API. SQLite tracks processed episodes to avoid duplicates.

**Tech Stack:** Python 3.14, uv, ruff, pytest, httpx, feedparser, pydub (FFmpeg), mutagen, google-genai, python-dotenv, asyncio

---

## File Structure

```
podcast-ad-remover/
├── pyproject.toml              # Project config: dependencies, ruff, pytest settings
├── Dockerfile                  # Python 3.14 slim + FFmpeg
├── docker-compose.yml          # Service definition alongside Audiobookshelf
├── config.toml.example         # Example configuration file
├── .env.example                # Example environment variables
├── src/
│   └── podcast_ad_remover/
│       ├── __init__.py         # Package marker (empty)
│       ├── __main__.py         # Entry point: load config, start scheduler
│       ├── models.py           # Shared dataclasses: AppConfig, FeedConfig, Episode, AdSegment
│       ├── config.py           # Load and validate config.toml + .env
│       ├── state.py            # SQLite state DB: track processed episodes
│       ├── feed.py             # Parse RSS feeds, return Episode objects
│       ├── downloader.py       # Download episode audio to temp files
│       ├── ad_detector.py      # Send audio to Gemini, parse ad timestamps
│       ├── audio_processor.py  # Cut ad segments from audio, export MP3
│       ├── audiobookshelf.py   # Audiobookshelf API client
│       ├── metadata.py         # Write ID3 tags to MP3 files
│       ├── pipeline.py         # Single-episode processing orchestration
│       └── scheduler.py        # Async polling loop
└── tests/
    ├── conftest.py             # Shared fixtures (tmp dirs, sample configs)
    ├── test_models.py          # Model validation tests
    ├── test_config.py          # Config loading/validation tests
    ├── test_state.py           # SQLite state tracking tests
    ├── test_feed.py            # RSS feed parsing tests
    ├── test_downloader.py      # Audio download tests
    ├── test_ad_detector.py     # Gemini integration tests (mocked)
    ├── test_audio_processor.py # Audio cutting/joining tests
    ├── test_audiobookshelf.py  # Audiobookshelf API client tests (mocked)
    ├── test_metadata.py        # ID3 tag writing tests
    ├── test_pipeline.py        # Episode processing pipeline tests
    └── test_scheduler.py       # Scheduler/polling loop tests
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/podcast_ad_remover/__init__.py`
- Create: `tests/__init__.py` (empty, needed for pytest discovery)
- Create: `tests/conftest.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "podcast-ad-remover"
version = "0.1.0"
description = "Remove ads from podcast episodes and upload to Audiobookshelf"
requires-python = ">=3.14"
dependencies = [
    "feedparser>=6.0",
    "httpx>=0.28",
    "pydub>=0.25",
    "mutagen>=1.47",
    "google-genai>=1.0",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.25",
    "respx>=0.22",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
target-version = "py314"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "W"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create directory structure and empty init files**

```bash
mkdir -p src/podcast_ad_remover tests
touch src/podcast_ad_remover/__init__.py tests/__init__.py
```

- [ ] **Step 3: Create tests/conftest.py with basic fixtures**

```python
import tempfile
from pathlib import Path

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
```

- [ ] **Step 4: Install dependencies and verify tooling works**

Run:
```bash
uv sync --all-extras
uv run ruff check src/ tests/
uv run pytest --co
```

Expected: All commands succeed. `ruff check` shows no errors. `pytest --co` shows "no tests ran" (no test files yet).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock src/ tests/
git commit -m "feat: project scaffolding with uv, ruff, and pytest"
```

---

### Task 2: Shared Models

**Files:**
- Create: `src/podcast_ad_remover/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for all model dataclasses**

`tests/test_models.py`:
```python
from podcast_ad_remover.models import AdSegment, AppConfig, AudiobookshelfConfig, Episode, FeedConfig


class TestFeedConfig:
    def test_create_minimal(self):
        feed = FeedConfig(url="https://example.com/feed.xml")
        assert feed.url == "https://example.com/feed.xml"
        assert feed.name is None
        assert feed.poll_interval_hours is None

    def test_create_full(self):
        feed = FeedConfig(
            url="https://example.com/feed.xml",
            name="My Podcast",
            poll_interval_hours=6,
        )
        assert feed.name == "My Podcast"
        assert feed.poll_interval_hours == 6


class TestAudiobookshelfConfig:
    def test_create(self):
        config = AudiobookshelfConfig(url="http://localhost:13378", library_id="lib-123")
        assert config.url == "http://localhost:13378"
        assert config.library_id == "lib-123"


class TestAppConfig:
    def test_create_with_defaults(self):
        config = AppConfig(
            audiobookshelf=AudiobookshelfConfig(url="http://localhost:13378", library_id="lib-123"),
            feeds=[FeedConfig(url="https://example.com/feed.xml")],
        )
        assert config.default_poll_interval_hours == 12.0

    def test_create_with_custom_interval(self):
        config = AppConfig(
            audiobookshelf=AudiobookshelfConfig(url="http://localhost:13378", library_id="lib-123"),
            feeds=[FeedConfig(url="https://example.com/feed.xml")],
            default_poll_interval_hours=6.0,
        )
        assert config.default_poll_interval_hours == 6.0


class TestEpisode:
    def test_create_minimal(self):
        ep = Episode(guid="ep-1", title="Episode 1", audio_url="https://example.com/ep1.mp3")
        assert ep.guid == "ep-1"
        assert ep.title == "Episode 1"
        assert ep.audio_url == "https://example.com/ep1.mp3"
        assert ep.description == ""
        assert ep.pub_date == ""
        assert ep.episode_number is None
        assert ep.season_number is None
        assert ep.episode_type == "full"

    def test_create_full(self):
        ep = Episode(
            guid="ep-1",
            title="Episode 1",
            audio_url="https://example.com/ep1.mp3",
            description="A great episode",
            pub_date="Mon, 25 Mar 2026 00:00:00 GMT",
            episode_number="5",
            season_number="2",
            episode_type="bonus",
        )
        assert ep.description == "A great episode"
        assert ep.episode_number == "5"
        assert ep.season_number == "2"
        assert ep.episode_type == "bonus"


class TestAdSegment:
    def test_create(self):
        seg = AdSegment(start=45.0, end=120.5)
        assert seg.start == 45.0
        assert seg.end == 120.5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'podcast_ad_remover.models'`

- [ ] **Step 3: Implement models**

`src/podcast_ad_remover/models.py`:
```python
from dataclasses import dataclass


@dataclass
class FeedConfig:
    url: str
    name: str | None = None
    poll_interval_hours: float | None = None


@dataclass
class AudiobookshelfConfig:
    url: str
    library_id: str


@dataclass
class AppConfig:
    audiobookshelf: AudiobookshelfConfig
    feeds: list[FeedConfig]
    default_poll_interval_hours: float = 12.0


@dataclass
class Episode:
    guid: str
    title: str
    audio_url: str
    description: str = ""
    pub_date: str = ""
    episode_number: str | None = None
    season_number: str | None = None
    episode_type: str = "full"


@dataclass
class AdSegment:
    start: float
    end: float
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_models.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Lint**

Run: `uv run ruff check src/podcast_ad_remover/models.py tests/test_models.py`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add src/podcast_ad_remover/models.py tests/test_models.py
git commit -m "feat: add shared dataclass models"
```

---

### Task 3: Config Module

**Files:**
- Create: `src/podcast_ad_remover/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests for config loading**

`tests/test_config.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'podcast_ad_remover.config'`

- [ ] **Step 3: Implement config module**

`src/podcast_ad_remover/config.py`:
```python
import tomllib
from pathlib import Path

from podcast_ad_remover.models import AppConfig, AudiobookshelfConfig, FeedConfig


def load_config(config_path: Path) -> AppConfig:
    """Load and validate configuration from a TOML file."""
    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    # Validate audiobookshelf section
    abs_section = raw.get("audiobookshelf")
    if not abs_section or not isinstance(abs_section, dict):
        raise ValueError("Config missing required section: [audiobookshelf]")
    if "url" not in abs_section:
        raise ValueError("Config [audiobookshelf] missing required field: url")
    if "library_id" not in abs_section:
        raise ValueError("Config [audiobookshelf] missing required field: library_id")

    audiobookshelf = AudiobookshelfConfig(
        url=abs_section["url"],
        library_id=abs_section["library_id"],
    )

    # Validate feeds
    raw_feeds = raw.get("feeds")
    if not raw_feeds or not isinstance(raw_feeds, list) or len(raw_feeds) == 0:
        raise ValueError("Config missing required section: [[feeds]]")

    feeds = []
    for i, raw_feed in enumerate(raw_feeds):
        if "url" not in raw_feed:
            raise ValueError(f"Config feeds[{i}] missing required field: url")
        feeds.append(
            FeedConfig(
                url=raw_feed["url"],
                name=raw_feed.get("name"),
                poll_interval_hours=raw_feed.get("poll_interval_hours"),
            )
        )

    # Defaults
    defaults = raw.get("defaults", {})
    default_poll_interval_hours = defaults.get("poll_interval_hours", 12.0)

    return AppConfig(
        audiobookshelf=audiobookshelf,
        feeds=feeds,
        default_poll_interval_hours=default_poll_interval_hours,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src/podcast_ad_remover/config.py tests/test_config.py
git add src/podcast_ad_remover/config.py tests/test_config.py
git commit -m "feat: add TOML config loading and validation"
```

---

### Task 4: State Module

**Files:**
- Create: `src/podcast_ad_remover/state.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: Write failing tests**

`tests/test_state.py`:
```python
import sqlite3

import pytest

from podcast_ad_remover.state import StateManager


@pytest.fixture
def state_db(tmp_path):
    db_path = tmp_path / "state.db"
    return StateManager(db_path)


class TestStateManager:
    def test_init_creates_table(self, state_db):
        """Database and table should be created on initialization."""
        conn = sqlite3.connect(state_db.db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='processed_episodes'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_is_processed_returns_false_for_unknown(self, state_db):
        assert state_db.is_processed("https://example.com/feed.xml", "ep-1") is False

    def test_mark_processed_then_is_processed(self, state_db):
        state_db.mark_processed("https://example.com/feed.xml", "ep-1", ad_segments_found=2)
        assert state_db.is_processed("https://example.com/feed.xml", "ep-1") is True

    def test_different_feeds_same_guid(self, state_db):
        state_db.mark_processed("https://example.com/feed1.xml", "ep-1", ad_segments_found=0)
        assert state_db.is_processed("https://example.com/feed1.xml", "ep-1") is True
        assert state_db.is_processed("https://example.com/feed2.xml", "ep-1") is False

    def test_mark_processed_with_fallback_status(self, state_db):
        state_db.mark_processed(
            "https://example.com/feed.xml", "ep-1", ad_segments_found=0, status="fallback"
        )
        assert state_db.is_processed("https://example.com/feed.xml", "ep-1") is True

    def test_mark_processed_duplicate_is_ignored(self, state_db):
        state_db.mark_processed("https://example.com/feed.xml", "ep-1", ad_segments_found=2)
        # Should not raise — duplicates are silently ignored
        state_db.mark_processed("https://example.com/feed.xml", "ep-1", ad_segments_found=3)
        assert state_db.is_processed("https://example.com/feed.xml", "ep-1") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'podcast_ad_remover.state'`

- [ ] **Step 3: Implement state module**

`src/podcast_ad_remover/state.py`:
```python
import sqlite3
from pathlib import Path


class StateManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    feed_url TEXT NOT NULL,
                    episode_guid TEXT NOT NULL,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ad_segments_found INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'success',
                    UNIQUE(feed_url, episode_guid)
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def is_processed(self, feed_url: str, episode_guid: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM processed_episodes WHERE feed_url = ? AND episode_guid = ?",
                (feed_url, episode_guid),
            )
            return cursor.fetchone() is not None

    def mark_processed(
        self,
        feed_url: str,
        episode_guid: str,
        ad_segments_found: int = 0,
        status: str = "success",
    ):
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO processed_episodes
                    (feed_url, episode_guid, ad_segments_found, status)
                VALUES (?, ?, ?, ?)
                """,
                (feed_url, episode_guid, ad_segments_found, status),
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_state.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src/podcast_ad_remover/state.py tests/test_state.py
git add src/podcast_ad_remover/state.py tests/test_state.py
git commit -m "feat: add SQLite state tracking for processed episodes"
```

---

### Task 5: Feed Module

**Files:**
- Create: `src/podcast_ad_remover/feed.py`
- Create: `tests/test_feed.py`

- [ ] **Step 1: Write failing tests**

`tests/test_feed.py`:
```python
from unittest.mock import patch

import pytest

from podcast_ad_remover.feed import parse_feed
from podcast_ad_remover.models import Episode


def _make_feed_dict(entries=None, title="Test Podcast", author="Test Author"):
    """Build a feedparser-like result dict."""
    return {
        "feed": {
            "title": title,
            "author": author,
            "subtitle": "A test podcast",
            "link": "https://example.com",
            "image": {"href": "https://example.com/cover.jpg"},
        },
        "entries": entries or [],
        "bozo": False,
    }


def _make_entry(
    guid="ep-1",
    title="Episode 1",
    audio_url="https://example.com/ep1.mp3",
    audio_type="audio/mpeg",
    summary="Episode summary",
    published="Mon, 25 Mar 2026 00:00:00 GMT",
    itunes_episode=None,
    itunes_season=None,
    itunes_episodetype="full",
):
    entry = {
        "id": guid,
        "title": title,
        "summary": summary,
        "published": published,
        "links": [
            {"rel": "enclosure", "href": audio_url, "type": audio_type},
        ],
    }
    if itunes_episode is not None:
        entry["itunes_episode"] = itunes_episode
    if itunes_season is not None:
        entry["itunes_season"] = itunes_season
    entry["itunes_episodetype"] = itunes_episodetype
    return entry


class TestParseFeed:
    @patch("podcast_ad_remover.feed.feedparser.parse")
    def test_parse_single_episode(self, mock_parse):
        mock_parse.return_value = _make_feed_dict(
            entries=[_make_entry()],
        )
        podcast_title, episodes = parse_feed("https://example.com/feed.xml")

        assert podcast_title == "Test Podcast"
        assert len(episodes) == 1
        ep = episodes[0]
        assert isinstance(ep, Episode)
        assert ep.guid == "ep-1"
        assert ep.title == "Episode 1"
        assert ep.audio_url == "https://example.com/ep1.mp3"
        assert ep.description == "Episode summary"
        assert ep.pub_date == "Mon, 25 Mar 2026 00:00:00 GMT"
        assert ep.episode_type == "full"

    @patch("podcast_ad_remover.feed.feedparser.parse")
    def test_parse_multiple_episodes_returns_oldest_first(self, mock_parse):
        mock_parse.return_value = _make_feed_dict(
            entries=[
                _make_entry(guid="ep-2", title="Newer", published="Tue, 26 Mar 2026 00:00:00 GMT"),
                _make_entry(guid="ep-1", title="Older", published="Mon, 25 Mar 2026 00:00:00 GMT"),
            ],
        )
        _, episodes = parse_feed("https://example.com/feed.xml")
        assert [e.guid for e in episodes] == ["ep-1", "ep-2"]

    @patch("podcast_ad_remover.feed.feedparser.parse")
    def test_parse_episode_with_itunes_metadata(self, mock_parse):
        mock_parse.return_value = _make_feed_dict(
            entries=[
                _make_entry(itunes_episode="5", itunes_season="2", itunes_episodetype="bonus"),
            ],
        )
        _, episodes = parse_feed("https://example.com/feed.xml")
        assert episodes[0].episode_number == "5"
        assert episodes[0].season_number == "2"
        assert episodes[0].episode_type == "bonus"

    @patch("podcast_ad_remover.feed.feedparser.parse")
    def test_parse_skips_non_audio_enclosures(self, mock_parse):
        entry = {
            "id": "ep-1",
            "title": "Episode 1",
            "summary": "",
            "published": "",
            "links": [
                {"rel": "enclosure", "href": "https://example.com/image.jpg", "type": "image/jpeg"},
            ],
        }
        mock_parse.return_value = _make_feed_dict(entries=[entry])
        _, episodes = parse_feed("https://example.com/feed.xml")
        assert len(episodes) == 0

    @patch("podcast_ad_remover.feed.feedparser.parse")
    def test_parse_empty_feed(self, mock_parse):
        mock_parse.return_value = _make_feed_dict(entries=[])
        _, episodes = parse_feed("https://example.com/feed.xml")
        assert episodes == []

    @patch("podcast_ad_remover.feed.feedparser.parse")
    def test_parse_bozo_feed_raises(self, mock_parse):
        result = _make_feed_dict()
        result["bozo"] = True
        result["bozo_exception"] = Exception("Malformed XML")
        mock_parse.return_value = result
        with pytest.raises(ValueError, match="Failed to parse"):
            parse_feed("https://example.com/feed.xml")

    @patch("podcast_ad_remover.feed.feedparser.parse")
    def test_parse_entry_missing_guid_uses_link(self, mock_parse):
        entry = {
            "link": "https://example.com/ep1",
            "title": "Episode 1",
            "summary": "",
            "published": "",
            "links": [
                {"rel": "enclosure", "href": "https://example.com/ep1.mp3", "type": "audio/mpeg"},
            ],
        }
        mock_parse.return_value = _make_feed_dict(entries=[entry])
        _, episodes = parse_feed("https://example.com/feed.xml")
        assert episodes[0].guid == "https://example.com/ep1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_feed.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'podcast_ad_remover.feed'`

- [ ] **Step 3: Implement feed module**

`src/podcast_ad_remover/feed.py`:
```python
import logging
from email.utils import parsedate_to_datetime

import feedparser

from podcast_ad_remover.models import Episode

logger = logging.getLogger(__name__)


def parse_feed(feed_url: str) -> tuple[str, list[Episode]]:
    """Parse an RSS feed and return (podcast_title, list of episodes oldest-first)."""
    result = feedparser.parse(feed_url)

    if result.get("bozo") and result.get("bozo_exception"):
        raise ValueError(f"Failed to parse feed {feed_url}: {result['bozo_exception']}")

    podcast_title = result.get("feed", {}).get("title", "Unknown Podcast")

    episodes = []
    for entry in result.get("entries", []):
        audio_url = _extract_audio_url(entry)
        if audio_url is None:
            logger.debug("Skipping entry %s — no audio enclosure", entry.get("title", "unknown"))
            continue

        guid = entry.get("id") or entry.get("link") or audio_url
        episodes.append(
            Episode(
                guid=guid,
                title=entry.get("title", ""),
                audio_url=audio_url,
                description=entry.get("summary", ""),
                pub_date=entry.get("published", ""),
                episode_number=entry.get("itunes_episode"),
                season_number=entry.get("itunes_season"),
                episode_type=entry.get("itunes_episodetype", "full"),
            )
        )

    # Sort oldest first by pub_date
    episodes.sort(key=_episode_sort_key)
    return podcast_title, episodes


def _extract_audio_url(entry: dict) -> str | None:
    """Find the first audio enclosure URL in a feed entry."""
    for link in entry.get("links", []):
        if link.get("rel") == "enclosure" and link.get("type", "").startswith("audio/"):
            return link["href"]
    return None


def _episode_sort_key(episode: Episode):
    """Sort key: parse pub_date to datetime, fallback to epoch 0."""
    if not episode.pub_date:
        return 0
    try:
        return parsedate_to_datetime(episode.pub_date).timestamp()
    except Exception:
        return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_feed.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src/podcast_ad_remover/feed.py tests/test_feed.py
git add src/podcast_ad_remover/feed.py tests/test_feed.py
git commit -m "feat: add RSS feed parsing with episode extraction"
```

---

### Task 6: Downloader Module

**Files:**
- Create: `src/podcast_ad_remover/downloader.py`
- Create: `tests/test_downloader.py`

- [ ] **Step 1: Write failing tests**

`tests/test_downloader.py`:
```python
import httpx
import pytest
import respx

from podcast_ad_remover.downloader import download_episode


class TestDownloadEpisode:
    @respx.mock
    def test_download_success(self, tmp_path):
        audio_content = b"\xff\xfb\x90\x00" * 100  # fake MP3 bytes
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_downloader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'podcast_ad_remover.downloader'`

- [ ] **Step 3: Implement downloader module**

`src/podcast_ad_remover/downloader.py`:
```python
import logging
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

logger = logging.getLogger(__name__)


def download_episode(audio_url: str, download_dir: Path) -> Path:
    """Download an episode audio file and return the local path."""
    parsed = urlparse(audio_url)
    filename = unquote(Path(parsed.path).name) or "episode.mp3"

    dest = download_dir / filename
    logger.info("Downloading %s to %s", audio_url, dest)

    with httpx.stream("GET", audio_url, follow_redirects=True) as response:
        response.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in response.iter_bytes(chunk_size=8192):
                f.write(chunk)

    logger.info("Downloaded %s (%d bytes)", filename, dest.stat().st_size)
    return dest
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_downloader.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src/podcast_ad_remover/downloader.py tests/test_downloader.py
git add src/podcast_ad_remover/downloader.py tests/test_downloader.py
git commit -m "feat: add episode audio downloader"
```

---

### Task 7: Ad Detector Module

**Files:**
- Create: `src/podcast_ad_remover/ad_detector.py`
- Create: `tests/test_ad_detector.py`

- [ ] **Step 1: Write failing tests**

`tests/test_ad_detector.py`:
```python
from pathlib import Path
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
        mock_response.text = '[{"begin": 10, "finish": 20}]'  # wrong keys
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ad_detector.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'podcast_ad_remover.ad_detector'`

- [ ] **Step 3: Implement ad detector module**

`src/podcast_ad_remover/ad_detector.py`:
```python
import json
import logging
from pathlib import Path

from google import genai
from google.genai import types

from podcast_ad_remover.models import AdSegment

logger = logging.getLogger(__name__)

PROMPT = """\
Listen to this podcast episode and identify all advertisement, sponsorship, \
and paid promotional segments. For each ad segment, provide the start and end \
timestamps in seconds.

Return your response as a JSON array of objects, where each object has "start" \
and "end" fields (in seconds, as floating-point numbers). If no advertisements \
are found, return an empty array [].

Example response:
[{"start": 45.0, "end": 120.5}, {"start": 1803.2, "end": 1920.0}]

Important:
- Only include actual advertisements, sponsorships, and paid promotional content.
- Do not include the podcast's own self-promotion or show notes.
- Timestamps should be as precise as possible.
- Return ONLY the JSON array, no other text.
"""


def detect_ads(audio_path: Path, api_key: str) -> list[AdSegment] | None:
    """Send audio to Gemini 2.5 Flash and return detected ad segments.

    Returns a list of AdSegment on success (may be empty if no ads found),
    or None if detection failed for any reason (API error, unparseable response).
    """
    uploaded_file = None
    try:
        client = genai.Client(api_key=api_key)

        logger.info("Uploading %s to Gemini for ad detection", audio_path.name)
        uploaded_file = client.files.upload(file=audio_path)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[uploaded_file, PROMPT],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        return _parse_response(response.text)

    except Exception:
        logger.exception("Ad detection failed for %s", audio_path.name)
        return None

    finally:
        if uploaded_file is not None:
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception:
                logger.warning("Failed to clean up uploaded file %s", uploaded_file.name)


def _parse_response(response_text: str) -> list[AdSegment] | None:
    """Parse the JSON response from Gemini into AdSegment objects.

    Returns a list on success (may be empty), or None on parse failure.
    """
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError:
        logger.warning("Gemini response is not valid JSON: %s", response_text[:200])
        return None

    if not isinstance(data, list):
        logger.warning("Gemini response is not a JSON array: %s", response_text[:200])
        return None

    segments = []
    for item in data:
        if not isinstance(item, dict) or "start" not in item or "end" not in item:
            logger.warning("Invalid ad segment format: %s", item)
            return None
        try:
            segments.append(AdSegment(start=float(item["start"]), end=float(item["end"])))
        except (TypeError, ValueError):
            logger.warning("Invalid ad segment values: %s", item)
            return None

    return segments
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ad_detector.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src/podcast_ad_remover/ad_detector.py tests/test_ad_detector.py
git add src/podcast_ad_remover/ad_detector.py tests/test_ad_detector.py
git commit -m "feat: add Gemini-based ad segment detection"
```

---

### Task 8: Audio Processor Module

**Files:**
- Create: `src/podcast_ad_remover/audio_processor.py`
- Create: `tests/test_audio_processor.py`

Note: These tests generate real (tiny) audio segments using pydub so that the processing logic is tested end-to-end. FFmpeg must be available.

- [ ] **Step 1: Write failing tests**

`tests/test_audio_processor.py`:
```python
import pytest
from pydub import AudioSegment
from pydub.generators import Sine

from podcast_ad_remover.audio_processor import remove_ads
from podcast_ad_remover.models import AdSegment


@pytest.fixture
def sample_audio(tmp_path):
    """Create a 10-second mono audio file at tmp_path/input.mp3."""
    # Generate 10 seconds of sine wave
    audio = Sine(440).to_audio_segment(duration=10000)  # 10s
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
        # Durations should be approximately equal (MP3 encoding may add padding)
        assert abs(len(result_audio) - len(original_audio)) < 100  # within 100ms

    def test_remove_single_segment(self, sample_audio, tmp_path):
        output = tmp_path / "output.mp3"
        # Remove 2s-4s from 10s audio → ~8s result
        segments = [AdSegment(start=2.0, end=4.0)]
        result = remove_ads(sample_audio, segments, output)
        assert result == output
        result_audio = AudioSegment.from_mp3(output)
        # 10s - 2s = ~8s (with MP3 padding tolerance)
        assert 7500 < len(result_audio) < 8500

    def test_remove_multiple_segments(self, sample_audio, tmp_path):
        output = tmp_path / "output.mp3"
        # Remove 1s-2s and 5s-7s from 10s → ~7s result
        segments = [AdSegment(start=1.0, end=2.0), AdSegment(start=5.0, end=7.0)]
        result = remove_ads(sample_audio, segments, output)
        result_audio = AudioSegment.from_mp3(output)
        assert 6500 < len(result_audio) < 7500

    def test_remove_segment_at_start(self, sample_audio, tmp_path):
        output = tmp_path / "output.mp3"
        segments = [AdSegment(start=0.0, end=3.0)]
        result = remove_ads(sample_audio, segments, output)
        result_audio = AudioSegment.from_mp3(output)
        assert 6500 < len(result_audio) < 7500

    def test_remove_segment_at_end(self, sample_audio, tmp_path):
        output = tmp_path / "output.mp3"
        segments = [AdSegment(start=8.0, end=10.0)]
        result = remove_ads(sample_audio, segments, output)
        result_audio = AudioSegment.from_mp3(output)
        assert 7500 < len(result_audio) < 8500

    def test_overlapping_segments_are_merged(self, sample_audio, tmp_path):
        output = tmp_path / "output.mp3"
        # Overlapping: 2-5 and 4-7 should merge to 2-7 → ~5s result
        segments = [AdSegment(start=2.0, end=5.0), AdSegment(start=4.0, end=7.0)]
        result = remove_ads(sample_audio, segments, output)
        result_audio = AudioSegment.from_mp3(output)
        assert 4500 < len(result_audio) < 5500

    def test_unsorted_segments_are_handled(self, sample_audio, tmp_path):
        output = tmp_path / "output.mp3"
        # Out of order: should still work
        segments = [AdSegment(start=5.0, end=7.0), AdSegment(start=1.0, end=2.0)]
        result = remove_ads(sample_audio, segments, output)
        result_audio = AudioSegment.from_mp3(output)
        assert 6500 < len(result_audio) < 7500

    def test_segment_beyond_duration_is_clamped(self, sample_audio, tmp_path):
        output = tmp_path / "output.mp3"
        # Segment extends past audio end
        segments = [AdSegment(start=8.0, end=15.0)]
        result = remove_ads(sample_audio, segments, output)
        result_audio = AudioSegment.from_mp3(output)
        assert 7500 < len(result_audio) < 8500
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_audio_processor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'podcast_ad_remover.audio_processor'`

- [ ] **Step 3: Implement audio processor**

`src/podcast_ad_remover/audio_processor.py`:
```python
import logging
from pathlib import Path

from pydub import AudioSegment

from podcast_ad_remover.models import AdSegment

logger = logging.getLogger(__name__)


def remove_ads(audio_path: Path, segments: list[AdSegment], output_path: Path) -> Path:
    """Remove ad segments from audio and export as MP3.

    Segments are sorted, merged if overlapping, and clamped to audio bounds.
    Non-ad portions are concatenated and exported to output_path.
    """
    audio = AudioSegment.from_file(audio_path)
    duration_s = len(audio) / 1000.0

    if not segments:
        audio.export(output_path, format="mp3")
        return output_path

    merged = _merge_segments(segments, duration_s)

    logger.info(
        "Removing %d ad segment(s) totaling %.1fs from %.1fs audio",
        len(merged),
        sum(s.end - s.start for s in merged),
        duration_s,
    )

    # Extract non-ad portions
    parts: list[AudioSegment] = []
    cursor_ms = 0
    for seg in merged:
        start_ms = int(seg.start * 1000)
        end_ms = int(seg.end * 1000)
        if start_ms > cursor_ms:
            parts.append(audio[cursor_ms:start_ms])
        cursor_ms = end_ms

    # Add remaining audio after last ad
    if cursor_ms < len(audio):
        parts.append(audio[cursor_ms:])

    if not parts:
        # Entire audio was ads — export silence rather than empty
        audio.export(output_path, format="mp3")
        return output_path

    result = parts[0]
    for part in parts[1:]:
        result = result + part

    result.export(output_path, format="mp3")
    return output_path


def _merge_segments(segments: list[AdSegment], duration_s: float) -> list[AdSegment]:
    """Sort, clamp to audio bounds, and merge overlapping segments."""
    # Clamp and filter
    clamped = []
    for s in segments:
        start = max(0.0, s.start)
        end = min(duration_s, s.end)
        if start < end:
            clamped.append(AdSegment(start=start, end=end))

    if not clamped:
        return []

    # Sort by start time
    clamped.sort(key=lambda s: s.start)

    # Merge overlapping
    merged = [clamped[0]]
    for seg in clamped[1:]:
        prev = merged[-1]
        if seg.start <= prev.end:
            merged[-1] = AdSegment(start=prev.start, end=max(prev.end, seg.end))
        else:
            merged.append(seg)

    return merged
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_audio_processor.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src/podcast_ad_remover/audio_processor.py tests/test_audio_processor.py
git add src/podcast_ad_remover/audio_processor.py tests/test_audio_processor.py
git commit -m "feat: add audio processor to cut ad segments from MP3s"
```

---

### Task 9: Audiobookshelf Client Module

**Files:**
- Create: `src/podcast_ad_remover/audiobookshelf.py`
- Create: `tests/test_audiobookshelf.py`

- [ ] **Step 1: Write failing tests**

`tests/test_audiobookshelf.py`:
```python
import httpx
import pytest
import respx

from podcast_ad_remover.audiobookshelf import AudiobookshelfClient


@pytest.fixture
def client():
    return AudiobookshelfClient(base_url="http://abs:13378", api_key="test-key")


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
                    "folders": [{"id": "fold-1", "fullPath": "/podcasts"}],
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
        result = client.find_podcast("lib-1", feed_url="https://example.com/feed.xml")
        assert result is not None

    @respx.mock
    def test_find_podcast_not_found(self, client):
        respx.get("http://abs:13378/api/libraries/lib-1/items").mock(
            return_value=httpx.Response(200, json={"results": [], "total": 0})
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
                    "folders": [{"id": "fold-1", "fullPath": "/podcasts"}],
                },
            )
        )
        respx.post("http://abs:13378/api/podcasts").mock(
            return_value=httpx.Response(
                200,
                json={"id": "li-new", "media": {"metadata": {"title": "New Podcast"}}},
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
        # Verify the request was made
        assert respx.calls.call_count == 1


class TestScanLibraryItem:
    @respx.mock
    def test_scan_library_item(self, client):
        respx.post("http://abs:13378/api/items/li-1/scan").mock(
            return_value=httpx.Response(200, json={"result": "UPDATED"})
        )
        client.scan_library_item("li-1")
        assert respx.calls.call_count == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_audiobookshelf.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'podcast_ad_remover.audiobookshelf'`

- [ ] **Step 3: Implement Audiobookshelf client**

`src/podcast_ad_remover/audiobookshelf.py`:
```python
import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


class AudiobookshelfClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )

    def get_library(self, library_id: str) -> dict:
        """Get library details including folders."""
        response = self._client.get(f"{self.base_url}/api/libraries/{library_id}")
        response.raise_for_status()
        return response.json()

    def find_podcast(
        self,
        library_id: str,
        title: str | None = None,
        feed_url: str | None = None,
    ) -> dict | None:
        """Find an existing podcast by title or feed URL. Returns None if not found."""
        response = self._client.get(
            f"{self.base_url}/api/libraries/{library_id}/items",
            params={"limit": 500},
        )
        response.raise_for_status()
        data = response.json()

        for item in data.get("results", []):
            metadata = item.get("media", {}).get("metadata", {})
            if feed_url and metadata.get("feedUrl") == feed_url:
                return item
            if title and metadata.get("title") == title:
                return item

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
        """Create a new podcast in Audiobookshelf."""
        library = self.get_library(library_id)
        folder = library["folders"][0]
        folder_id = folder["id"]
        folder_path = folder["fullPath"]
        podcast_path = f"{folder_path}/{title}"

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
        """Upload an audio file to an existing podcast."""
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
        """Trigger a scan of a specific library item to detect new episodes."""
        logger.info("Scanning library item %s", library_item_id)
        response = self._client.post(f"{self.base_url}/api/items/{library_item_id}/scan")
        response.raise_for_status()

    def close(self):
        self._client.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_audiobookshelf.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src/podcast_ad_remover/audiobookshelf.py tests/test_audiobookshelf.py
git add src/podcast_ad_remover/audiobookshelf.py tests/test_audiobookshelf.py
git commit -m "feat: add Audiobookshelf API client"
```

---

### Task 10: ID3 Metadata Module

**Files:**
- Create: `src/podcast_ad_remover/metadata.py`
- Create: `tests/test_metadata.py`

- [ ] **Step 1: Write failing tests**

`tests/test_metadata.py`:
```python
import pytest
from mutagen.id3 import ID3
from pydub import AudioSegment
from pydub.generators import Sine

from podcast_ad_remover.metadata import write_id3_tags
from podcast_ad_remover.models import Episode


@pytest.fixture
def mp3_file(tmp_path):
    """Create a minimal MP3 file."""
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
            guid="ep-1",
            title="My Episode",
            audio_url="https://example.com/ep.mp3",
            description="Episode description",
        )
        write_id3_tags(mp3_file, episode)

        tags = ID3(mp3_file)
        # Description stored in comment frame
        assert "Episode description" in str(tags.get("COMM::eng") or tags.get("COMM::\x00\x00\x00"))

    def test_writes_episode_number(self, mp3_file):
        episode = Episode(
            guid="ep-1",
            title="My Episode",
            audio_url="https://example.com/ep.mp3",
            episode_number="42",
        )
        write_id3_tags(mp3_file, episode)

        tags = ID3(mp3_file)
        assert str(tags["TRCK"]) == "42"

    def test_writes_pub_date(self, mp3_file):
        episode = Episode(
            guid="ep-1",
            title="My Episode",
            audio_url="https://example.com/ep.mp3",
            pub_date="Mon, 25 Mar 2026 00:00:00 GMT",
        )
        write_id3_tags(mp3_file, episode)

        tags = ID3(mp3_file)
        assert "2026" in str(tags["TDRC"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_metadata.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'podcast_ad_remover.metadata'`

- [ ] **Step 3: Implement metadata module**

`src/podcast_ad_remover/metadata.py`:
```python
import logging
from email.utils import parsedate_to_datetime
from pathlib import Path

from mutagen.id3 import COMM, TDRC, TIT2, TRCK, ID3, ID3NoHeaderError

from podcast_ad_remover.models import Episode

logger = logging.getLogger(__name__)


def write_id3_tags(audio_path: Path, episode: Episode):
    """Write episode metadata as ID3 tags to an MP3 file."""
    try:
        tags = ID3(audio_path)
    except ID3NoHeaderError:
        tags = ID3()

    tags["TIT2"] = TIT2(encoding=3, text=episode.title)

    if episode.description:
        tags["COMM"] = COMM(encoding=3, lang="eng", desc="", text=episode.description)

    if episode.episode_number:
        tags["TRCK"] = TRCK(encoding=3, text=episode.episode_number)

    if episode.pub_date:
        try:
            dt = parsedate_to_datetime(episode.pub_date)
            tags["TDRC"] = TDRC(encoding=3, text=str(dt.year))
        except Exception:
            logger.debug("Could not parse pub_date for ID3: %s", episode.pub_date)

    tags.save(audio_path)
    logger.debug("Wrote ID3 tags to %s", audio_path.name)
```

- [ ] **Step 4: Run metadata tests**

Run: `uv run pytest tests/test_metadata.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src/podcast_ad_remover/metadata.py tests/test_metadata.py
git add src/podcast_ad_remover/metadata.py tests/test_metadata.py
git commit -m "feat: add ID3 metadata tag writer"
```

---

### Task 11: Episode Processing Pipeline

**Files:**
- Create: `src/podcast_ad_remover/pipeline.py`
- Create: `tests/test_pipeline.py`

This module orchestrates processing of a single episode: download → detect ads → cut audio → write metadata → upload.

- [ ] **Step 1: Write failing tests**

`tests/test_pipeline.py`:
```python
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from podcast_ad_remover.models import AdSegment, Episode
from podcast_ad_remover.pipeline import process_episode


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


class TestProcessEpisode:
    @patch("podcast_ad_remover.pipeline.write_id3_tags")
    @patch("podcast_ad_remover.pipeline.remove_ads")
    @patch("podcast_ad_remover.pipeline.detect_ads")
    @patch("podcast_ad_remover.pipeline.download_episode")
    def test_success_with_ads(self, mock_download, mock_detect, mock_remove, mock_tags, episode, fake_audio, tmp_path):
        mock_download.return_value = fake_audio
        mock_detect.return_value = [AdSegment(start=10.0, end=20.0)]
        processed_path = tmp_path / "processed.mp3"
        processed_path.write_bytes(b"processed")
        mock_remove.return_value = processed_path

        abs_client = MagicMock()
        abs_client.find_podcast.return_value = {"id": "li-1", "media": {"metadata": {"title": "Podcast"}}}
        abs_client.get_library.return_value = {"folders": [{"id": "fold-1", "fullPath": "/podcasts"}]}

        state = MagicMock()
        state.is_processed.return_value = False

        result = process_episode(
            episode=episode,
            feed_url="https://example.com/feed.xml",
            podcast_title="Podcast",
            library_id="lib-1",
            gemini_api_key="gem-key",
            abs_client=abs_client,
            state=state,
            work_dir=tmp_path,
        )

        assert result is True
        mock_download.assert_called_once()
        mock_detect.assert_called_once()
        mock_remove.assert_called_once()
        abs_client.upload_episode.assert_called_once()
        abs_client.scan_library_item.assert_called_once_with("li-1")
        state.mark_processed.assert_called_once_with(
            "https://example.com/feed.xml", "ep-1", ad_segments_found=1, status="success"
        )

    @patch("podcast_ad_remover.pipeline.write_id3_tags")
    @patch("podcast_ad_remover.pipeline.detect_ads")
    @patch("podcast_ad_remover.pipeline.download_episode")
    def test_fallback_on_detection_failure(self, mock_download, mock_detect, mock_tags, episode, fake_audio, tmp_path):
        mock_download.return_value = fake_audio
        mock_detect.return_value = None  # Detection failed

        abs_client = MagicMock()
        abs_client.find_podcast.return_value = {"id": "li-1", "media": {"metadata": {"title": "Podcast"}}}
        abs_client.get_library.return_value = {"folders": [{"id": "fold-1", "fullPath": "/podcasts"}]}

        state = MagicMock()
        state.is_processed.return_value = False

        result = process_episode(
            episode=episode,
            feed_url="https://example.com/feed.xml",
            podcast_title="Podcast",
            library_id="lib-1",
            gemini_api_key="gem-key",
            abs_client=abs_client,
            state=state,
            work_dir=tmp_path,
        )

        assert result is True
        abs_client.upload_episode.assert_called_once()
        state.mark_processed.assert_called_once_with(
            "https://example.com/feed.xml", "ep-1", ad_segments_found=0, status="fallback"
        )

    @patch("podcast_ad_remover.pipeline.write_id3_tags")
    @patch("podcast_ad_remover.pipeline.detect_ads")
    @patch("podcast_ad_remover.pipeline.download_episode")
    def test_no_ads_found_uploads_original(self, mock_download, mock_detect, mock_tags, episode, fake_audio, tmp_path):
        mock_download.return_value = fake_audio
        mock_detect.return_value = []  # No ads in this episode (detection succeeded)

        abs_client = MagicMock()
        abs_client.find_podcast.return_value = {"id": "li-1", "media": {"metadata": {"title": "Podcast"}}}
        abs_client.get_library.return_value = {"folders": [{"id": "fold-1", "fullPath": "/podcasts"}]}

        state = MagicMock()
        state.is_processed.return_value = False

        result = process_episode(
            episode=episode,
            feed_url="https://example.com/feed.xml",
            podcast_title="Podcast",
            library_id="lib-1",
            gemini_api_key="gem-key",
            abs_client=abs_client,
            state=state,
            work_dir=tmp_path,
        )

        assert result is True
        abs_client.upload_episode.assert_called_once()
        state.mark_processed.assert_called_once_with(
            "https://example.com/feed.xml", "ep-1", ad_segments_found=0, status="success"
        )

    @patch("podcast_ad_remover.pipeline.download_episode")
    def test_skips_already_processed(self, mock_download, episode, tmp_path):
        abs_client = MagicMock()
        state = MagicMock()
        state.is_processed.return_value = True

        result = process_episode(
            episode=episode,
            feed_url="https://example.com/feed.xml",
            podcast_title="Podcast",
            library_id="lib-1",
            gemini_api_key="gem-key",
            abs_client=abs_client,
            state=state,
            work_dir=tmp_path,
        )

        assert result is False
        mock_download.assert_not_called()

    @patch("podcast_ad_remover.pipeline.write_id3_tags")
    @patch("podcast_ad_remover.pipeline.detect_ads")
    @patch("podcast_ad_remover.pipeline.download_episode")
    def test_upload_failure_does_not_mark_processed(self, mock_download, mock_detect, mock_tags, episode, fake_audio, tmp_path):
        mock_download.return_value = fake_audio
        mock_detect.return_value = None

        abs_client = MagicMock()
        abs_client.find_podcast.return_value = {"id": "li-1", "media": {"metadata": {"title": "Podcast"}}}
        abs_client.get_library.return_value = {"folders": [{"id": "fold-1", "fullPath": "/podcasts"}]}
        abs_client.upload_episode.side_effect = Exception("Upload failed")

        state = MagicMock()
        state.is_processed.return_value = False

        with pytest.raises(Exception, match="Upload failed"):
            process_episode(
                episode=episode,
                feed_url="https://example.com/feed.xml",
                podcast_title="Podcast",
                library_id="lib-1",
                gemini_api_key="gem-key",
                abs_client=abs_client,
                state=state,
                work_dir=tmp_path,
            )

        state.mark_processed.assert_not_called()

    @patch("podcast_ad_remover.pipeline.write_id3_tags")
    @patch("podcast_ad_remover.pipeline.detect_ads")
    @patch("podcast_ad_remover.pipeline.download_episode")
    def test_creates_podcast_if_not_found(self, mock_download, mock_detect, mock_tags, episode, fake_audio, tmp_path):
        mock_download.return_value = fake_audio
        mock_detect.return_value = []
        abs_client = MagicMock()
        abs_client.find_podcast.return_value = None
        abs_client.create_podcast.return_value = {"id": "li-new"}
        abs_client.get_library.return_value = {"folders": [{"id": "fold-1", "fullPath": "/podcasts"}]}

        state = MagicMock()
        state.is_processed.return_value = False

        process_episode(
            episode=episode,
            feed_url="https://example.com/feed.xml",
            podcast_title="Podcast",
            library_id="lib-1",
            gemini_api_key="gem-key",
            abs_client=abs_client,
            state=state,
            work_dir=tmp_path,
        )

        abs_client.create_podcast.assert_called_once_with(
            library_id="lib-1",
            title="Podcast",
            feed_url="https://example.com/feed.xml",
        )

    @patch("podcast_ad_remover.pipeline.write_id3_tags")
    @patch("podcast_ad_remover.pipeline.detect_ads")
    @patch("podcast_ad_remover.pipeline.download_episode")
    def test_scan_failure_does_not_prevent_marking_processed(self, mock_download, mock_detect, mock_tags, episode, fake_audio, tmp_path):
        mock_download.return_value = fake_audio
        mock_detect.return_value = None

        abs_client = MagicMock()
        abs_client.find_podcast.return_value = {"id": "li-1", "media": {"metadata": {"title": "Podcast"}}}
        abs_client.get_library.return_value = {"folders": [{"id": "fold-1", "fullPath": "/podcasts"}]}
        abs_client.scan_library_item.side_effect = Exception("Scan failed")

        state = MagicMock()
        state.is_processed.return_value = False

        result = process_episode(
            episode=episode,
            feed_url="https://example.com/feed.xml",
            podcast_title="Podcast",
            library_id="lib-1",
            gemini_api_key="gem-key",
            abs_client=abs_client,
            state=state,
            work_dir=tmp_path,
        )

        assert result is True
        state.mark_processed.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'podcast_ad_remover.pipeline'`

- [ ] **Step 3: Implement pipeline module**

`src/podcast_ad_remover/pipeline.py`:
```python
import logging
from pathlib import Path

from podcast_ad_remover.ad_detector import detect_ads
from podcast_ad_remover.audio_processor import remove_ads
from podcast_ad_remover.audiobookshelf import AudiobookshelfClient
from podcast_ad_remover.downloader import download_episode
from podcast_ad_remover.metadata import write_id3_tags
from podcast_ad_remover.models import Episode
from podcast_ad_remover.state import StateManager

logger = logging.getLogger(__name__)


def process_episode(
    episode: Episode,
    feed_url: str,
    podcast_title: str,
    library_id: str,
    gemini_api_key: str,
    abs_client: AudiobookshelfClient,
    state: StateManager,
    work_dir: Path,
) -> bool:
    """Process a single podcast episode. Returns True if processed, False if skipped."""
    if state.is_processed(feed_url, episode.guid):
        logger.debug("Skipping already-processed episode: %s", episode.title)
        return False

    logger.info("Processing episode: %s", episode.title)

    # Download
    download_dir = work_dir / "downloads"
    download_dir.mkdir(exist_ok=True)
    audio_path = download_episode(episode.audio_url, download_dir)

    # Detect ads (None = detection failed, [] = no ads found, [...] = ads found)
    segments = detect_ads(audio_path, api_key=gemini_api_key)

    # Process audio
    if segments is None:
        # Detection failed — upload original as fallback
        upload_path = audio_path
        status = "fallback"
        ad_count = 0
    elif segments:
        # Ads found — cut them out
        output_dir = work_dir / "processed"
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / audio_path.name
        upload_path = remove_ads(audio_path, segments, output_path)
        status = "success"
        ad_count = len(segments)
    else:
        # No ads found (clean episode) — upload original
        upload_path = audio_path
        status = "success"
        ad_count = 0

    # Write ID3 metadata
    write_id3_tags(upload_path, episode)

    # Ensure podcast exists in Audiobookshelf
    podcast_item = abs_client.find_podcast(library_id, title=podcast_title, feed_url=feed_url)
    if podcast_item is None:
        podcast_item = abs_client.create_podcast(
            library_id=library_id,
            title=podcast_title,
            feed_url=feed_url,
        )

    library_item_id = podcast_item["id"]

    # Get folder ID
    library = abs_client.get_library(library_id)
    folder_id = library["folders"][0]["id"]

    # Upload
    abs_client.upload_episode(
        library_id=library_id,
        folder_id=folder_id,
        podcast_title=podcast_title,
        audio_path=upload_path,
    )

    # Trigger scan to detect the new episode (best-effort, don't fail on scan error)
    try:
        abs_client.scan_library_item(library_item_id)
    except Exception:
        logger.warning("Failed to trigger scan for library item %s", library_item_id)

    # Mark as processed (only after successful upload)
    state.mark_processed(
        feed_url,
        episode.guid,
        ad_segments_found=ad_count,
        status=status,
    )

    logger.info(
        "Episode '%s' processed: %d ad segments removed (status: %s)",
        episode.title,
        ad_count,
        status,
    )
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src/podcast_ad_remover/pipeline.py tests/test_pipeline.py
git add src/podcast_ad_remover/pipeline.py tests/test_pipeline.py
git commit -m "feat: add episode processing pipeline"
```

---

### Task 12: Scheduler Module

**Files:**
- Create: `src/podcast_ad_remover/scheduler.py`
- Create: `tests/test_scheduler.py`

- [ ] **Step 1: Write failing tests**

`tests/test_scheduler.py`:
```python
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from podcast_ad_remover.models import AppConfig, AudiobookshelfConfig, Episode, FeedConfig
from podcast_ad_remover.scheduler import Scheduler


@pytest.fixture
def app_config():
    return AppConfig(
        audiobookshelf=AudiobookshelfConfig(url="http://abs:13378", library_id="lib-1"),
        feeds=[
            FeedConfig(url="https://example.com/feed.xml"),
            FeedConfig(url="https://example.com/other.xml", name="Custom", poll_interval_hours=1),
        ],
        default_poll_interval_hours=12.0,
    )


@pytest.fixture
def scheduler(app_config):
    return Scheduler(
        config=app_config,
        abs_api_key="abs-key",
        gemini_api_key="gem-key",
        data_dir="/tmp/test-data",
    )


class TestScheduler:
    def test_effective_poll_interval(self, scheduler):
        # First feed: no override → uses default (12h)
        assert scheduler._effective_interval_seconds(scheduler.config.feeds[0]) == 12.0 * 3600

        # Second feed: override to 1h
        assert scheduler._effective_interval_seconds(scheduler.config.feeds[1]) == 1.0 * 3600

    @patch("podcast_ad_remover.scheduler.parse_feed")
    @patch("podcast_ad_remover.scheduler.process_episode")
    def test_poll_feed_processes_new_episodes(self, mock_process, mock_parse, scheduler):
        mock_parse.return_value = (
            "Test Podcast",
            [
                Episode(guid="ep-1", title="Ep 1", audio_url="https://example.com/ep1.mp3"),
                Episode(guid="ep-2", title="Ep 2", audio_url="https://example.com/ep2.mp3"),
            ],
        )
        mock_process.return_value = True

        feed = FeedConfig(url="https://example.com/feed.xml")
        scheduler.poll_feed(feed)

        assert mock_process.call_count == 2

    @patch("podcast_ad_remover.scheduler.parse_feed")
    @patch("podcast_ad_remover.scheduler.process_episode")
    def test_poll_feed_uses_custom_name(self, mock_process, mock_parse, scheduler):
        mock_parse.return_value = ("RSS Title", [
            Episode(guid="ep-1", title="Ep 1", audio_url="https://example.com/ep1.mp3"),
        ])
        mock_process.return_value = True

        feed = FeedConfig(url="https://example.com/feed.xml", name="Custom Name")
        scheduler.poll_feed(feed)

        # podcast_title arg should be the custom name, not RSS title
        call_kwargs = mock_process.call_args[1]
        assert call_kwargs["podcast_title"] == "Custom Name"

    @patch("podcast_ad_remover.scheduler.parse_feed")
    def test_poll_feed_continues_on_episode_error(self, mock_parse, scheduler):
        mock_parse.return_value = (
            "Test Podcast",
            [
                Episode(guid="ep-1", title="Ep 1", audio_url="https://example.com/ep1.mp3"),
                Episode(guid="ep-2", title="Ep 2", audio_url="https://example.com/ep2.mp3"),
            ],
        )

        with patch("podcast_ad_remover.scheduler.process_episode") as mock_process:
            mock_process.side_effect = [Exception("download failed"), True]
            scheduler.poll_feed(FeedConfig(url="https://example.com/feed.xml"))
            # Should still try second episode after first fails
            assert mock_process.call_count == 2

    @patch("podcast_ad_remover.scheduler.parse_feed")
    def test_poll_feed_handles_feed_error(self, mock_parse, scheduler):
        mock_parse.side_effect = ValueError("Malformed XML")
        # Should not raise
        scheduler.poll_feed(FeedConfig(url="https://example.com/feed.xml"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scheduler.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'podcast_ad_remover.scheduler'`

- [ ] **Step 3: Implement scheduler module**

`src/podcast_ad_remover/scheduler.py`:
```python
import asyncio
import logging
import tempfile
from pathlib import Path

from podcast_ad_remover.audiobookshelf import AudiobookshelfClient
from podcast_ad_remover.feed import parse_feed
from podcast_ad_remover.models import AppConfig, FeedConfig
from podcast_ad_remover.pipeline import process_episode
from podcast_ad_remover.state import StateManager

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(
        self,
        config: AppConfig,
        abs_api_key: str,
        gemini_api_key: str,
        data_dir: str | Path,
    ):
        self.config = config
        self.gemini_api_key = gemini_api_key
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.state = StateManager(self.data_dir / "state.db")
        self.abs_client = AudiobookshelfClient(
            base_url=config.audiobookshelf.url,
            api_key=abs_api_key,
        )

    def _effective_interval_seconds(self, feed: FeedConfig) -> float:
        hours = feed.poll_interval_hours or self.config.default_poll_interval_hours
        return hours * 3600

    def poll_feed(self, feed: FeedConfig):
        """Poll a single feed and process all new episodes."""
        try:
            podcast_title, episodes = parse_feed(feed.url)
        except Exception:
            logger.exception("Failed to fetch feed: %s", feed.url)
            return

        # Use custom name if set
        display_name = feed.name or podcast_title

        logger.info("Polled '%s': %d episodes found", display_name, len(episodes))

        for episode in episodes:
            try:
                with tempfile.TemporaryDirectory() as work_dir:
                    process_episode(
                        episode=episode,
                        feed_url=feed.url,
                        podcast_title=display_name,
                        library_id=self.config.audiobookshelf.library_id,
                        gemini_api_key=self.gemini_api_key,
                        abs_client=self.abs_client,
                        state=self.state,
                        work_dir=Path(work_dir),
                    )
            except Exception:
                logger.exception(
                    "Failed to process episode '%s' from '%s'", episode.title, display_name
                )

    async def run(self):
        """Start the polling loop for all feeds."""
        logger.info("Starting scheduler with %d feeds", len(self.config.feeds))

        tasks = [self._feed_loop(feed) for feed in self.config.feeds]
        try:
            await asyncio.gather(*tasks)
        finally:
            self.abs_client.close()

    async def _feed_loop(self, feed: FeedConfig):
        """Polling loop for a single feed."""
        interval = self._effective_interval_seconds(feed)
        name = feed.name or feed.url

        logger.info("Starting poll loop for '%s' (every %.1f hours)", name, interval / 3600)

        while True:
            logger.info("Polling feed: %s", name)
            await asyncio.to_thread(self.poll_feed, feed)
            logger.info("Next poll for '%s' in %.1f hours", name, interval / 3600)
            await asyncio.sleep(interval)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_scheduler.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src/podcast_ad_remover/scheduler.py tests/test_scheduler.py
git add src/podcast_ad_remover/scheduler.py tests/test_scheduler.py
git commit -m "feat: add async scheduler with per-feed polling loops"
```

---

### Task 13: Entry Point

**Files:**
- Create: `src/podcast_ad_remover/__main__.py`

- [ ] **Step 1: Implement entry point**

`src/podcast_ad_remover/__main__.py`:
```python
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from podcast_ad_remover.config import load_config
from podcast_ad_remover.scheduler import Scheduler


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )
    logger = logging.getLogger("podcast_ad_remover")

    # Load .env
    load_dotenv()

    # Load config
    config_path = Path(os.getenv("CONFIG_PATH", "config.toml"))
    if not config_path.exists():
        logger.error("Config file not found: %s", config_path)
        sys.exit(1)

    try:
        config = load_config(config_path)
    except (ValueError, FileNotFoundError) as e:
        logger.error("Invalid configuration: %s", e)
        sys.exit(1)

    # Read API keys
    abs_api_key = os.getenv("AUDIOBOOKSHELF_API_KEY")
    if not abs_api_key:
        logger.error("AUDIOBOOKSHELF_API_KEY not set in environment")
        sys.exit(1)

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        logger.error("GEMINI_API_KEY not set in environment")
        sys.exit(1)

    data_dir = Path(os.getenv("DATA_DIR", "data"))

    logger.info("Starting Podcast Ad Remover")
    logger.info("Audiobookshelf: %s", config.audiobookshelf.url)
    logger.info("Feeds: %d configured", len(config.feeds))

    scheduler = Scheduler(
        config=config,
        abs_api_key=abs_api_key,
        gemini_api_key=gemini_api_key,
        data_dir=data_dir,
    )

    asyncio.run(scheduler.run())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify it at least imports and shows help-like error**

Run: `uv run python -m podcast_ad_remover 2>&1 || true`
Expected: Should log an error about missing config or API keys (since we have no config.toml), then exit 1. This confirms the entry point loads.

- [ ] **Step 3: Lint and commit**

```bash
uv run ruff check src/podcast_ad_remover/__main__.py
git add src/podcast_ad_remover/__main__.py
git commit -m "feat: add application entry point"
```

---

### Task 14: Docker and Deployment Files

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `config.toml.example`
- Create: `.env.example`

- [ ] **Step 1: Create Dockerfile**

`Dockerfile`:
```dockerfile
FROM python:3.14-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

COPY src/ src/

CMD ["uv", "run", "python", "-m", "podcast_ad_remover"]
```

- [ ] **Step 2: Create docker-compose.yml**

`docker-compose.yml`:
```yaml
services:
  podcast-ad-remover:
    build: .
    env_file: .env
    volumes:
      - ./config.toml:/app/config.toml:ro
      - podcast-ad-remover-data:/app/data
    restart: unless-stopped

volumes:
  podcast-ad-remover-data:
```

- [ ] **Step 3: Create example config files**

`config.toml.example`:
```toml
[audiobookshelf]
url = "http://audiobookshelf:13378"
library_id = "your-library-id-here"

[defaults]
poll_interval_hours = 12

[[feeds]]
url = "https://example.com/podcast/feed.xml"

# [[feeds]]
# url = "https://example.com/another/feed.xml"
# name = "Custom Display Name"
# poll_interval_hours = 6
```

`.env.example`:
```
AUDIOBOOKSHELF_API_KEY=your-audiobookshelf-api-key
GEMINI_API_KEY=your-gemini-api-key
```

- [ ] **Step 4: Create .gitignore**

`.gitignore`:
```
__pycache__/
*.pyc
.env
data/
*.egg-info/
dist/
.ruff_cache/
.pytest_cache/
```

- [ ] **Step 5: Commit**

```bash
git add Dockerfile docker-compose.yml config.toml.example .env.example .gitignore
git commit -m "feat: add Docker and deployment configuration"
```

---

### Task 15: Full Test Suite Verification

- [ ] **Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: All tests PASS (approximately 50 tests across 10 test files)

- [ ] **Step 2: Run linter on entire codebase**

Run: `uv run ruff check src/ tests/`
Expected: No errors

- [ ] **Step 3: Verify Docker build (if Docker is available)**

Run: `docker build -t podcast-ad-remover . 2>&1 | tail -5`
Expected: Build completes successfully

- [ ] **Step 4: Final commit if any fixes were needed**

```bash
git add -A
git status
# Only commit if there are changes
```

---

## Dependency Graph

```
Task 1  (scaffolding)
  └─▶ Task 2  (models)
       ├─▶ Task 3  (config)
       ├─▶ Task 4  (state)
       ├─▶ Task 5  (feed)
       ├─▶ Task 6  (downloader)
       ├─▶ Task 7  (ad detector)
       ├─▶ Task 8  (audio processor)
       ├─▶ Task 9  (audiobookshelf client)
       └─▶ Task 10 (metadata)
            └─▶ Task 11 (pipeline)     ◀── depends on Tasks 4-10
                 └─▶ Task 12 (scheduler)
                      └─▶ Task 13 (entry point)
                           └─▶ Task 14 (docker)
                                └─▶ Task 15 (full verification)
```

Tasks 3-10 can be implemented in parallel after Task 2 completes.
Task 11 (pipeline) depends on all component modules (Tasks 4-10).
