"""Utility helpers for the compilations domain."""

import uuid


def build_output_key(compilation_id: uuid.UUID) -> str:
    """Return the storage key for a compilation's rendered MP4 output."""
    return f"outputs/{compilation_id}.mp4"


def truncate_stderr(text: str, max_chars: int = 2000) -> str:
    """Return the last max_chars characters of text, or the full text if shorter.

    Used to capture the most relevant tail of FFmpeg stderr output without
    storing unbounded strings in the database or SSE payload.  Note: ffmpeg.py
    already line-truncates stderr to 20 lines before this function is called;
    this is a character-length safety net on top of that.
    """
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]
