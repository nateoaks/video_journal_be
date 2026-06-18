"""Pure helpers for the clips domain."""

import uuid

from app.common.exceptions import UnsupportedMediaTypeError

ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".mov", ".mp4", ".m4v"})


def safe_extension(filename: str | None) -> str:
    """Return the lowercased extension for filename, validated against allowed types.

    Raises UnsupportedMediaTypeError if the filename is missing, empty, or has an
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


def build_original_key(clip_id: uuid.UUID, ext: str) -> str:
    """Return the storage key for the raw uploaded clip file."""
    return f"clips/original/{clip_id}{ext}"
