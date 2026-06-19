"""Unit tests for compilations domain utility helpers."""

from app.domains.compilations.utils import truncate_stderr


def test_truncate_stderr_empty_string() -> None:
    """Empty string is returned unchanged."""
    assert truncate_stderr("") == ""


def test_truncate_stderr_short_string_unchanged() -> None:
    """A string shorter than max_chars is returned as-is."""
    text = "short error message"
    assert truncate_stderr(text) == text


def test_truncate_stderr_exactly_max_chars_unchanged() -> None:
    """A string exactly equal to max_chars is returned unchanged."""
    text = "x" * 2000
    assert truncate_stderr(text) == text


def test_truncate_stderr_oversized_returns_tail() -> None:
    """A string longer than max_chars is capped to the last max_chars characters."""
    prefix = "a" * 500
    tail = "b" * 2000
    text = prefix + tail
    result = truncate_stderr(text)
    assert len(result) == 2000
    assert result == tail


def test_truncate_stderr_custom_max_chars() -> None:
    """max_chars parameter is respected."""
    text = "hello world"
    result = truncate_stderr(text, max_chars=5)
    assert result == "world"


def test_truncate_stderr_preserves_newlines_in_tail() -> None:
    """Newlines within the tail are preserved (FFmpeg stderr has newlines)."""
    lines = "\n".join([f"line {i}" for i in range(100)])
    result = truncate_stderr(lines, max_chars=50)
    assert len(result) == 50
    assert result == lines[-50:]
