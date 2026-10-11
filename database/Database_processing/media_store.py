"""
ConvoEase - Media Store
Uploaded images and audio live in the database, so they survive redeploys on
hosts whose disks are wiped (most free tiers).
"""

import uuid

from sqlalchemy import insert, select

from config import setup_logging
from .db_manager import DBManager, media, utc_now

logger = setup_logging("media_store")

# Recognise real file content from its first bytes instead of trusting the
# client's MIME type, so nothing else can be served back as an "image".
_IMAGE_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"GIF87a", "image/gif", "gif"),
    (b"GIF89a", "image/gif", "gif"),
    (b"BM", "image/bmp", "bmp"),
)

_AUDIO_TYPES = {
    "mp3": "audio/mpeg",
    "m4a": "audio/mp4",
    "wav": "audio/wav",
    "ogg": "audio/ogg",
    "opus": "audio/ogg",
    "flac": "audio/flac",
    "webm": "audio/webm",
    "aac": "audio/aac",
}


def sniff_image(data):
    """Return (mime_type, extension) for a supported image, or (None, None)."""
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    for signature, mime_type, ext in _IMAGE_SIGNATURES:
        if data.startswith(signature):
            return mime_type, ext
    return None, None


def audio_format(mime_type):
    """Map a browser audio MIME type to (extension, canonical mime) or (None, None)."""
    fmt = (mime_type or "").split("/")[-1].split(";")[0].lower().strip()
    aliases = {"mpeg": "mp3", "mp4": "m4a", "x-m4a": "m4a", "x-wav": "wav", "wave": "wav", "vnd.wave": "wav"}
    fmt = aliases.get(fmt, fmt)
    if fmt not in _AUDIO_TYPES:
        return None, None
    return fmt, _AUDIO_TYPES[fmt]


class MediaStore:
    @staticmethod
    def save(kind, group_id, username, data, mime_type, ext):
        """Store bytes and return the public URL path, e.g. /media/image/<id>.png"""
        media_id = f"{uuid.uuid4()}.{ext}"
        DBManager.execute(insert(media).values(
            media_id=media_id,
            kind=kind,
            group_id=group_id,
            username=username,
            mime_type=mime_type,
            size=len(data),
            data=data,
            created_at=utc_now(),
        ))
        logger.info("Stored %s %s (%d bytes) for group %s", kind, media_id, len(data), group_id)
        return f"/media/{kind}/{media_id}"

    @staticmethod
    def get(kind, media_id):
        row = DBManager.fetch_one(select(media).where(media.c.media_id == media_id))
        if not row or row["kind"] != kind:
            return None
        return row
