# podcast-ad-remover

A podcast pre-processor that automatically removes ads from podcast episodes before adding them to [Audiobookshelf](https://www.audiobookshelf.org/).

The application polls configured RSS feeds on a schedule, downloads new episodes, sends the audio to Gemini 2.5 Flash to identify ad segments, cuts those segments out, and uploads the cleaned episodes to Audiobookshelf with their original metadata preserved. If ad detection fails for any reason, the original unmodified episode is uploaded as a fallback.

## How It Works

```
RSS Feed → Download Episode → Gemini Ad Detection → Remove Ad Segments → Upload to Audiobookshelf
```

1. Polls your configured podcast RSS feeds at regular intervals
2. Downloads new episodes it hasn't seen before
3. Sends the audio to Gemini 2.5 Flash, which identifies ad segment timestamps
4. Cuts out the ad segments using FFmpeg (hard cuts, no crossfades)
5. Writes episode metadata as ID3 tags to the processed MP3
6. Uploads the cleaned episode to your Audiobookshelf server
7. Tracks processed episodes in a local SQLite database to avoid duplicates

If Gemini can't identify ads (API error, unparseable response), the original episode is uploaded unchanged.

## Prerequisites

- An [Audiobookshelf](https://www.audiobookshelf.org/) server with a podcast library
- A [Google AI API key](https://ai.google.dev/) for Gemini 2.5 Flash
- Docker and Docker Compose (for containerized deployment), or Python 3.14+ and FFmpeg (for local use)

## Quick Start (Docker Compose)

1. Clone the repository:

   ```bash
   git clone https://github.com/your-username/podcast-ad-remover.git
   cd podcast-ad-remover
   ```

2. Create your configuration:

   ```bash
   cp config.toml.example config.toml
   cp .env.example .env
   ```

3. Edit `.env` with your API keys:

   ```
   AUDIOBOOKSHELF_API_KEY=your-audiobookshelf-api-key
   GEMINI_API_KEY=your-gemini-api-key
   ```

4. Edit `config.toml` with your Audiobookshelf server URL, library ID, and podcast feeds:

   ```toml
   [audiobookshelf]
   url = "http://audiobookshelf:13378"
   library_id = "your-library-id"

   [[feeds]]
   url = "https://example.com/podcast/feed.xml"
   ```

5. Start the container:

   ```bash
   docker compose up -d
   ```

The application will immediately poll all configured feeds on startup, then continue polling at the configured interval (default: every 12 hours).

## Configuration

### config.toml

```toml
[audiobookshelf]
url = "http://audiobookshelf:13378"   # Audiobookshelf server URL
library_id = "your-library-id"        # Target podcast library ID

[defaults]
poll_interval_hours = 12              # Default polling interval (optional, default: 12)

[[feeds]]
url = "https://example.com/podcast/feed.xml"

[[feeds]]
url = "https://example.com/another/feed.xml"
name = "Custom Display Name"          # Override the podcast name (optional)
poll_interval_hours = 6               # Override polling interval for this feed (optional)
earliest_episode = 2025-01-01         # Ignore episodes published before this date (optional)
```

### Environment Variables

| Variable | Description |
|---|---|
| `AUDIOBOOKSHELF_API_KEY` | API key for your Audiobookshelf server |
| `GEMINI_API_KEY` | Google AI API key for Gemini 2.5 Flash |
| `CONFIG_PATH` | Path to config file (default: `config.toml`) |
| `DATA_DIR` | Directory for SQLite state database (default: `data`) |

### Finding Your Audiobookshelf Library ID

In the Audiobookshelf web UI, navigate to your podcast library. The library ID is in the URL: `http://your-server/library/<library-id>`.

## Running Locally

Requires Python 3.14+ and FFmpeg.

```bash
# Install dependencies
uv sync --all-extras

# Create config and .env (see Quick Start steps 2-4)

# Run
uv run python -m podcast_ad_remover
```

## Development

```bash
# Install all dependencies including dev tools
uv sync --all-extras

# Run tests
uv run pytest -v

# Run linter
uv run ruff check src/ tests/

# Run a specific test file
uv run pytest tests/test_audio_processor.py -v
```

### Project Structure

```
src/podcast_ad_remover/
├── __main__.py          # Entry point
├── models.py            # Shared dataclasses
├── config.py            # TOML config loading
├── state.py             # SQLite processed-episode tracking
├── feed.py              # RSS feed parsing
├── downloader.py        # Episode audio downloading
├── ad_detector.py       # Gemini API integration
├── audio_processor.py   # Ad segment removal (pydub/FFmpeg)
├── metadata.py          # ID3 tag writing
├── audiobookshelf.py    # Audiobookshelf API client
├── pipeline.py          # Single-episode processing orchestration
└── scheduler.py         # Async polling loop
```

### Architecture

The application is structured as a pipeline of independent modules:

- **Scheduler** manages per-feed async polling loops
- **Feed** parses RSS and returns Episode objects sorted oldest-first
- **Pipeline** orchestrates the processing of a single episode
- **Ad Detector** sends audio to Gemini and parses timestamp responses
- **Audio Processor** cuts segments using pydub and merges remaining portions
- **Audiobookshelf Client** handles API communication (find/create podcasts, upload episodes)
- **State Manager** tracks processed episodes in SQLite to survive restarts

### Failure Handling

| Failure | Behavior |
|---|---|
| Gemini API error or unparseable response | Upload original episode unchanged |
| Audiobookshelf upload failure | Skip episode, retry on next poll |
| RSS feed fetch failure | Skip this poll cycle, retry on next |
| Episode download failure | Skip episode, retry on next poll |

## Docker Compose with Audiobookshelf

If you run Audiobookshelf in Docker, add podcast-ad-remover to the same compose file:

```yaml
services:
  audiobookshelf:
    image: ghcr.io/advplyr/audiobookshelf:latest
    ports:
      - "13378:80"
    volumes:
      - ./audiobooks:/audiobooks
      - ./podcasts:/podcasts
      - ./config:/config
      - ./metadata:/metadata

  podcast-ad-remover:
    build: ./podcast-ad-remover
    env_file: ./podcast-ad-remover/.env
    volumes:
      - ./podcast-ad-remover/config.toml:/app/config.toml:ro
      - podcast-ad-remover-data:/app/data
    restart: unless-stopped

volumes:
  podcast-ad-remover-data:
```

Use `http://audiobookshelf:80` as the `url` in `config.toml` when both services share a Docker network.

## License

MIT
