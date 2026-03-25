# podcast-ad-remover

A podcast pre-processor that automatically removes ads from podcast episodes before adding them to [Audiobookshelf](https://www.audiobookshelf.org/).

The application polls configured RSS feeds on a schedule, downloads new episodes, sends the audio to Gemini 2.5 Flash to identify ad segments, cuts those segments out, and uploads the cleaned episodes to Audiobookshelf with their original metadata preserved. If ad detection fails for any reason, the original unmodified episode is uploaded as a fallback.

Designed to run as a Docker container alongside Audiobookshelf via Docker Compose.
