import logging
from pathlib import Path

from pydub import AudioSegment

from podcast_ad_remover.models import AdSegment

logger = logging.getLogger(__name__)


def remove_ads(audio_path: Path, segments: list[AdSegment], output_path: Path) -> Path:
    audio = AudioSegment.from_file(audio_path)
    duration_s = len(audio) / 1000.0
    if not segments:
        audio.export(output_path, format="mp3")
        return output_path
    merged = _merge_segments(segments, duration_s)
    logger.info(
        "Removing %d ad segment(s) totaling %.1fs from %.1fs audio",
        len(merged), sum(s.end - s.start for s in merged), duration_s,
    )
    parts: list[AudioSegment] = []
    cursor_ms = 0
    for seg in merged:
        start_ms = int(seg.start * 1000)
        end_ms = int(seg.end * 1000)
        if start_ms > cursor_ms:
            parts.append(audio[cursor_ms:start_ms])
        cursor_ms = end_ms
    if cursor_ms < len(audio):
        parts.append(audio[cursor_ms:])
    if not parts:
        audio.export(output_path, format="mp3")
        return output_path
    result = parts[0]
    for part in parts[1:]:
        result = result + part
    result.export(output_path, format="mp3")
    return output_path


AD_GAP_BRIDGE_THRESHOLD = 5.0  # seconds


def _merge_segments(segments: list[AdSegment], duration_s: float) -> list[AdSegment]:
    """Sort, clamp, merge overlapping segments, and bridge small gaps between ads."""
    clamped = []
    for s in segments:
        start = max(0.0, s.start)
        end = min(duration_s, s.end)
        if start < end:
            clamped.append(AdSegment(start=start, end=end))
    if not clamped:
        return []
    clamped.sort(key=lambda s: s.start)
    # Merge overlapping
    merged = [clamped[0]]
    for seg in clamped[1:]:
        prev = merged[-1]
        if seg.start <= prev.end:
            merged[-1] = AdSegment(start=prev.start, end=max(prev.end, seg.end))
        else:
            merged.append(seg)
    # Bridge small gaps between consecutive ad segments
    bridged = [merged[0]]
    for seg in merged[1:]:
        prev = bridged[-1]
        gap = seg.start - prev.end
        if gap <= AD_GAP_BRIDGE_THRESHOLD:
            bridged[-1] = AdSegment(start=prev.start, end=seg.end)
        else:
            bridged.append(seg)
    return bridged
