import json
import logging
from pathlib import Path

from google import genai
from google.genai import types

from podcast_ad_remover.models import AdSegment

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """\
Listen to this podcast episode and identify all advertisement, sponsorship, \
and paid promotional segments. For each ad segment, provide the start and end \
timestamps in seconds.
{podcast_context}
Ads commonly appear:
- At the very beginning of the episode (pre-roll), before the hosts start talking. \
Pre-roll ads often start at timestamp 0.0.
- In the middle of the episode (mid-roll), interrupting the main content.
- At the end of the episode (post-roll), often running to the very end of the audio.
- Each ad break typically contains multiple ~30-second ads back-to-back.

Use audio characteristics to help identify ad boundaries:
- Ads are typically more heavily produced and compressed than conversational \
podcast content — they sound louder, more polished, and have less dynamic range.
- Transitions between ads and program content are often marked by brief silences, \
jingles, or a noticeable shift in audio quality or production style.
- Ad segments often feature different speakers (voice-over artists) who do not \
appear in the main program content.
- The main program typically sounds like a natural conversation with varying \
volume, pauses, and a more relaxed production style.

Return your response as a JSON array of objects, where each object has "start" \
and "end" fields (in seconds, as floating-point numbers). If no advertisements \
are found, return an empty array [].

Example response:
[{{"start": 0.0, "end": 65.0}}, {{"start": 1803.2, "end": 1920.0}}]

Important:
- Ads can start at timestamp 0.0 — do not skip the beginning of the episode.
- Only include actual advertisements, sponsorships, and paid promotional content.
- Do not include the podcast's own self-promotion or show notes.
- Timestamps should be as precise as possible.
- Return ONLY the JSON array, no other text.
"""


def _build_prompt(podcast_title: str | None = None, podcast_description: str | None = None) -> str:
    if podcast_title or podcast_description:
        lines = ["\nThis podcast's subject matter:"]
        if podcast_title:
            lines.append(f"- Title: {podcast_title}")
        if podcast_description:
            lines.append(f"- Description: {podcast_description}")
        lines.append(
            "Any content NOT related to this subject is more likely to be an advertisement.\n"
        )
        context = "\n".join(lines)
    else:
        context = ""
    return PROMPT_TEMPLATE.format(podcast_context=context)


def detect_ads(
    audio_path: Path,
    api_key: str,
    client: genai.Client | None = None,
    podcast_title: str | None = None,
    podcast_description: str | None = None,
) -> list[AdSegment] | None:
    """Send audio to Gemini 2.5 Flash and return detected ad segments.

    Returns a list of AdSegment on success (may be empty if no ads found),
    or None if detection failed for any reason (API error, unparseable response).
    Pass an existing client to avoid creating a new one per call.
    """
    uploaded_file = None
    try:
        if client is None:
            client = genai.Client(api_key=api_key)
        logger.info("Uploading %s to Gemini for ad detection", audio_path.name)
        uploaded_file = client.files.upload(file=audio_path)
        prompt = _build_prompt(podcast_title, podcast_description)
        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=[uploaded_file, prompt],
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
