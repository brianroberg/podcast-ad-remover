# Podcast Ad Remover — Application Specification

## Overview

A Python application that acts as a pre-processor for podcast RSS feeds. It polls configured feeds on a schedule, downloads new episodes, uses Gemini 2.5 Flash to identify ad segments, removes those segments from the audio, and uploads the cleaned episodes to an Audiobookshelf server.

Deployed as a Docker container alongside Audiobookshelf via Docker Compose.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌────────────────┐
│  RSS Feed   │────▶│  Downloader  │────▶│  Ad Detect  │────▶│ Audio Splitter │
│  Poller     │     │              │     │ (Gemini API)│     │  (pydub/ffmpeg)│
└─────────────┘     └──────────────┘     └─────────────┘     └───────┬────────┘
                                                                      │
                    ┌──────────────┐     ┌─────────────┐              │
                    │   SQLite     │◀───▶│ Audiobookshelf│◀────────────┘
                    │   State DB   │     │   Uploader   │
                    └──────────────┘     └─────────────┘
```

### Components

1. **Scheduler** — Long-lived process that manages per-feed polling timers.
2. **Feed Poller** — Parses RSS feeds and identifies new (unprocessed) episodes.
3. **Episode Downloader** — Downloads episode audio files to a temporary directory.
4. **Ad Detector** — Sends audio to Gemini 2.5 Flash and parses ad segment timestamps from the response.
5. **Audio Processor** — Uses pydub (backed by FFmpeg) to cut ad segments and concatenate remaining portions into a single MP3 file. Hard cuts, no crossfades.
6. **Audiobookshelf Client** — Creates podcasts and uploads episodes via the Audiobookshelf API.
7. **State Manager** — SQLite database tracking which episodes have been processed.

## Configuration

### TOML Config File (`config.toml`)

```toml
[audiobookshelf]
url = "http://audiobookshelf:13378"
library_id = "your-library-id"

[defaults]
poll_interval_hours = 12

[[feeds]]
url = "https://example.com/podcast/feed.xml"

[[feeds]]
url = "https://example.com/another/feed.xml"
name = "My Custom Podcast Name"
poll_interval_hours = 6
```

#### Fields

- `audiobookshelf.url` (required) — Base URL of the Audiobookshelf server.
- `audiobookshelf.library_id` (required) — ID of the podcast library in Audiobookshelf where episodes will be uploaded.
- `defaults.poll_interval_hours` (optional, default: `12`) — Default polling interval for all feeds.
- `feeds` (required, array) — List of podcast feeds to process.
  - `feeds.url` (required) — RSS feed URL.
  - `feeds.name` (optional) — Custom display name for the podcast. If omitted, uses the title from the RSS feed.
  - `feeds.poll_interval_hours` (optional) — Per-feed polling interval override.

### Environment Variables (`.env`)

```
AUDIOBOOKSHELF_API_KEY=your-audiobookshelf-api-key
GEMINI_API_KEY=your-gemini-api-key
```

## Behavior

### Startup

1. Load and validate `config.toml`.
2. Load environment variables from `.env`.
3. Initialize (or open) the SQLite state database.
4. For each configured feed, schedule the first poll immediately, then repeat at the feed's configured interval.

### Poll Cycle (per feed)

1. Fetch and parse the RSS feed.
2. Compare episode GUIDs against the state database to identify new episodes.
3. For each new episode (oldest first):
   a. Download the audio file to a temporary directory.
   b. Send the audio to Gemini 2.5 Flash with a prompt requesting ad segment timestamps.
   c. Parse the Gemini response to extract ad segment start/end times.
   d. If ad segments were identified and parsed successfully:
      - Cut the ad segments from the audio using pydub.
      - Concatenate the remaining portions into a single MP3 file.
   e. If Gemini fails, returns no segments, or returns unparseable output:
      - Log a warning.
      - Use the original unmodified audio file as the upload candidate.
   f. Ensure the podcast exists in Audiobookshelf (create if needed).
   g. Upload the processed (or original) audio file to Audiobookshelf with episode metadata.
   h. Record the episode GUID in the state database as processed.

### Failure Handling

- **Gemini API failure or unparseable response**: Upload unmodified episode. Log warning.
- **Audiobookshelf upload failure**: Log error. Do NOT mark the episode as processed, so it will be retried on the next poll cycle.
- **Feed fetch failure**: Log error. Skip this poll cycle for the feed; retry on next scheduled poll.
- **Download failure**: Log error. Skip the episode for this cycle; retry on next poll.

## Audiobookshelf API Integration

Authentication: `Authorization: Bearer <AUDIOBOOKSHELF_API_KEY>` header on all requests.

### Endpoints Used

1. **List library items** — `GET /api/libraries/{libraryId}/items`
   - Used to check if a podcast already exists in the library.
   - Match by feed URL or podcast title.

2. **Create podcast** — `POST /api/podcasts`
   - Request body:
     ```json
     {
       "libraryId": "uuid",
       "folderId": "uuid",
       "path": "/podcasts/Podcast Title",
       "media": {
         "metadata": {
           "title": "Podcast Title",
           "author": "Author",
           "description": "Description",
           "feedUrl": "https://example.com/feed.xml"
         }
       }
     }
     ```
   - Used when a podcast doesn't yet exist in Audiobookshelf.

3. **Upload episode** — `POST /api/upload`
   - Multipart form data with the audio file and metadata.
   - Fields: `library`, `folder`, `title`, `author`.

4. **Get library folders** — `GET /api/libraries/{libraryId}`
   - Used to discover the folder ID for uploads.

### Episode Metadata Preserved

The following metadata from the RSS feed is passed along to Audiobookshelf:

- Title
- Description
- Publication date
- Episode number (if present)
- Season number (if present)
- Episode type (full, trailer, bonus)

## Gemini Integration

### Model

Gemini 2.5 Flash (`gemini-2.5-flash`) via the Google GenAI API.

### Prompt Strategy

Send the audio file to Gemini with a structured prompt requesting identification of ad/commercial segments. The prompt will instruct the model to return a JSON array of objects with `start` and `end` fields (in seconds).

Example expected response format:
```json
[
  {"start": 45.0, "end": 120.5},
  {"start": 1803.2, "end": 1920.0}
]
```

### Error Handling

- If the response is not valid JSON or doesn't match the expected schema, treat as "no ads found" and upload the original audio.
- If the API call fails (rate limit, network error, etc.), treat as "no ads found" and upload the original audio.

## State Database (SQLite)

### Schema

```sql
CREATE TABLE processed_episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feed_url TEXT NOT NULL,
    episode_guid TEXT NOT NULL,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ad_segments_found INTEGER DEFAULT 0,
    status TEXT DEFAULT 'success',
    UNIQUE(feed_url, episode_guid)
);
```

### Fields

- `feed_url` — The RSS feed URL the episode belongs to.
- `episode_guid` — The unique GUID from the RSS feed entry.
- `processed_at` — When the episode was processed.
- `ad_segments_found` — Number of ad segments detected and removed.
- `status` — `'success'` or `'fallback'` (if original audio was uploaded due to detection failure).

## Technology Stack

- **Language**: Python 3.14
- **Package manager**: uv
- **Linter**: ruff
- **RSS parsing**: `feedparser`
- **Audio processing**: `pydub` (requires FFmpeg in the container)
- **HTTP client**: `httpx` (async-capable, modern)
- **Gemini API**: `google-genai` (Google's official GenAI SDK)
- **Config parsing**: `tomllib` (stdlib)
- **Environment variables**: `python-dotenv`
- **State storage**: `sqlite3` (stdlib)
- **Logging**: `logging` (stdlib), output to stdout
- **Scheduling**: `asyncio` with `asyncio.sleep`-based loop (no external dependency)

## Deployment

### Dockerfile

- Base image: Python 3.14 slim
- Install FFmpeg via apt
- Install dependencies via uv
- Copy application code
- Entrypoint: `python -m podcast_ad_remover`

### Docker Compose

```yaml
services:
  podcast-ad-remover:
    build: .
    env_file: .env
    volumes:
      - ./config.toml:/app/config.toml:ro
      - podcast-ad-remover-data:/app/data  # SQLite DB location
    restart: unless-stopped

volumes:
  podcast-ad-remover-data:
```

The Audiobookshelf service definition would be in the user's existing compose file; this service can be added alongside it. If both are in the same compose file, the `audiobookshelf.url` in config would use the Docker service name (e.g., `http://audiobookshelf:13378`).

## Project Structure

```
podcast-ad-remover/
├── pyproject.toml
├── Dockerfile
├── config.toml.example
├── .env.example
├── src/
│   └── podcast_ad_remover/
│       ├── __init__.py
│       ├── __main__.py          # Entry point
│       ├── config.py            # TOML config loading & validation
│       ├── scheduler.py         # Poll scheduling loop
│       ├── feed.py              # RSS feed parsing
│       ├── downloader.py        # Episode audio downloading
│       ├── ad_detector.py       # Gemini API integration
│       ├── audio_processor.py   # pydub-based ad removal
│       ├── audiobookshelf.py    # Audiobookshelf API client
│       └── state.py             # SQLite state management
└── tests/
    ├── conftest.py
    ├── test_config.py
    ├── test_feed.py
    ├── test_downloader.py
    ├── test_ad_detector.py
    ├── test_audio_processor.py
    ├── test_audiobookshelf.py
    ├── test_state.py
    └── test_scheduler.py
```

## Development Methodology

Red/green TDD:
1. Write a failing test for the next piece of behavior.
2. Write the minimum code to make the test pass.
3. Refactor if needed.
4. Repeat.

Tests will use `pytest`. External dependencies (Gemini API, Audiobookshelf API, RSS feeds) will be mocked in unit tests.
