"""Pure helpers for the soundtracks domain."""

import uuid
from pathlib import Path

from fastapi import HTTPException

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

MAX_RANGE_HEADER_LEN = 64


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


def parse_range_header(header: str | None, file_size: int) -> tuple[int, int] | None:
    """Parse an HTTP Range header and return (start, end) inclusive byte offsets.

    Returns None if no header is provided.
    Raises HTTPException(416) for unsatisfiable or malformed ranges.
    """
    if header is None:
        return None

    if len(header) > MAX_RANGE_HEADER_LEN:
        raise HTTPException(status_code=416, detail="Range header too long")

    if not header.startswith("bytes="):
        raise HTTPException(status_code=416, detail="Invalid Range header format")

    range_spec = header[len("bytes=") :]
    parts = range_spec.split("-", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=416, detail="Invalid Range header format")

    start_str, end_str = parts[0].strip(), parts[1].strip()

    # Handle suffix-range: bytes=-N means last N bytes.
    if not start_str:
        try:
            suffix_len = int(end_str)
        except ValueError as exc:
            raise HTTPException(
                status_code=416, detail="Invalid Range suffix value"
            ) from exc
        start = max(0, file_size - suffix_len)
        end = file_size - 1
        return start, end

    try:
        start = int(start_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=416, detail="Invalid Range start value"
        ) from exc

    if end_str == "":
        end = file_size - 1
    else:
        try:
            end = int(end_str)
        except ValueError as exc:
            raise HTTPException(
                status_code=416, detail="Invalid Range end value"
            ) from exc

    if start < 0 or end < start or start >= file_size:
        raise HTTPException(
            status_code=416,
            detail=f"Range {start}-{end} is not satisfiable for file size {file_size}",
        )

    # Clamp end to file_size - 1.
    end = min(end, file_size - 1)

    return start, end
