"""Pure helpers for the soundtracks domain."""

import uuid
from pathlib import Path

from app.common.exceptions import UnsupportedMediaTypeError

ALLOWED_EXTENSIONS: frozenset[str] = frozenset(
    {".mp3", ".m4a", ".aac", ".wav", ".flac"}
)

CONTENT_TYPES: dict[str, str] = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
}


def safe_extension(filename: str | None) -> str:
    """Return the lowercased extension for filename, validated against allowed types.

    Raises UnsupportedMediaTypeError(415) if the filename is missing, empty, or has an
    extension that is not in ALLOWED_EXTENSIONS.
    """
    if not filename:
        raise UnsupportedMediaTypeError("Filename is required")

    dot_pos = filename.rfind(".")
    if dot_pos == -1:
        raise UnsupportedMediaTypeError(
            f"File has no extension; allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    ext = "." + filename[dot_pos + 1 :].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise UnsupportedMediaTypeError(
            f"Extension '{ext}' is not allowed; allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    return ext


def build_soundtrack_key(soundtrack_id: uuid.UUID, ext: str) -> str:
    """Return the storage key for a soundtrack file."""
    return f"soundtracks/{soundtrack_id}{ext}"


def title_from_filename(filename: str) -> str:
    """Return the filename stem (name without extension) as a fallback title."""
    return Path(filename).stem
