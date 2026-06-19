"""Unit tests for app.media.normalize."""

from app.media.normalize import build_normalize_command


def test_build_normalize_command_contains_expected_args() -> None:
    """build_normalize_command returns a list with the full canonical recipe."""
    cmd = build_normalize_command("in.mp4", "out.mp4")

    assert "ffmpeg" in cmd
    assert "-y" in cmd
    assert "in.mp4" in cmd
    assert "out.mp4" in cmd
    assert "libx264" in cmd
    assert "-crf" in cmd
    assert "18" in cmd
    assert "-preset" in cmd
    assert "medium" in cmd
    assert "yuv420p" in cmd
    assert "-r" in cmd
    assert "30" in cmd
    assert "-vsync" in cmd
    assert "cfr" in cmd
    assert "aac" in cmd
    assert "192k" in cmd
    assert "+faststart" in cmd
