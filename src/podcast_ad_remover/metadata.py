import logging
from email.utils import parsedate_to_datetime
from pathlib import Path

from mutagen.id3 import COMM, ID3, TDRC, TIT2, TRCK, ID3NoHeaderError

from podcast_ad_remover.models import Episode

logger = logging.getLogger(__name__)


def write_id3_tags(audio_path: Path, episode: Episode):
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
            tags["TDRC"] = TDRC(encoding=3, text=dt.strftime("%Y-%m-%dT%H:%M:%S"))
        except Exception:
            logger.debug("Could not parse pub_date for ID3: %s", episode.pub_date)

    tags.save(audio_path)
    logger.debug("Wrote ID3 tags to %s", audio_path.name)
