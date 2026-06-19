"""Unit tests for app.media.filmstrip."""

import pytest

from app.media.filmstrip import (
    build_filmstrip_command,
    compute_frame_count,
    generate_filmstrip,
)

# ---------------------------------------------------------------------------
# compute_frame_count
# ---------------------------------------------------------------------------


def test_compute_frame_count_none_returns_1() -> None:
    """Unknown duration → always at least 1 frame."""
    assert compute_frame_count(None) == 1


def test_compute_frame_count_zero_returns_1() -> None:
    """Zero duration is treated the same as unknown."""
    assert compute_frame_count(0.0) == 1


def test_compute_frame_count_negative_returns_1() -> None:
    """Negative duration is treated the same as unknown."""
    assert compute_frame_count(-5.0) == 1


def test_compute_frame_count_sub_second_returns_1() -> None:
    """Duration < 1 s → floor is 0, so clamped to 1."""
    assert compute_frame_count(0.5) == 1


def test_compute_frame_count_exactly_1s() -> None:
    """1 s clip → 1 frame."""
    assert compute_frame_count(1.0) == 1


def test_compute_frame_count_5s() -> None:
    """5 s clip → 5 frames."""
    assert compute_frame_count(5.0) == 5


def test_compute_frame_count_9s() -> None:
    """9 s clip → 9 frames."""
    assert compute_frame_count(9.0) == 9


def test_compute_frame_count_10s() -> None:
    """10 s clip → 10 frames (max)."""
    assert compute_frame_count(10.0) == 10


def test_compute_frame_count_long_clip_capped_at_10() -> None:
    """Long clip → capped at 10."""
    assert compute_frame_count(120.0) == 10


def test_compute_frame_count_fractional_rounds_down() -> None:
    """9.9 s → floor is 9, not 10."""
    assert compute_frame_count(9.9) == 9


# ---------------------------------------------------------------------------
# build_filmstrip_command
# ---------------------------------------------------------------------------


def test_build_filmstrip_command_contains_input_and_output() -> None:
    """Command must contain src and dst paths."""
    cmd = build_filmstrip_command("in.mp4", "out.jpg", duration_s=10.0, frame_count=10)
    assert "in.mp4" in cmd
    assert "out.jpg" in cmd


def test_build_filmstrip_command_starts_with_ffmpeg() -> None:
    """First element must be the ffmpeg binary."""
    cmd = build_filmstrip_command("in.mp4", "out.jpg", duration_s=10.0, frame_count=10)
    assert cmd[0] == "ffmpeg"


def test_build_filmstrip_command_overwrite_flag() -> None:
    """Command must include -y to overwrite without prompting."""
    cmd = build_filmstrip_command("in.mp4", "out.jpg", duration_s=10.0, frame_count=10)
    assert "-y" in cmd


def test_build_filmstrip_command_single_frame_output() -> None:
    """Command must request only 1 output frame via -frames:v 1."""
    cmd = build_filmstrip_command("in.mp4", "out.jpg", duration_s=10.0, frame_count=10)
    assert "-frames:v" in cmd
    idx = cmd.index("-frames:v")
    assert cmd[idx + 1] == "1"


def test_build_filmstrip_command_vf_contains_fps() -> None:
    """Video filter must include an fps expression."""
    cmd = build_filmstrip_command("in.mp4", "out.jpg", duration_s=10.0, frame_count=5)
    vf = _get_vf(cmd)
    assert "fps=" in vf


def test_build_filmstrip_command_vf_scale_height_72() -> None:
    """Thumbnail height must be 72 px."""
    cmd = build_filmstrip_command("in.mp4", "out.jpg", duration_s=10.0, frame_count=5)
    vf = _get_vf(cmd)
    assert "scale=-1:72" in vf


def test_build_filmstrip_command_vf_tile() -> None:
    """Tile filter must lay frames out horizontally."""
    cmd = build_filmstrip_command("in.mp4", "out.jpg", duration_s=10.0, frame_count=5)
    vf = _get_vf(cmd)
    assert "tile=5x1" in vf


def test_build_filmstrip_command_vf_tile_matches_frame_count() -> None:
    """Tile width must match frame_count exactly."""
    cmd = build_filmstrip_command("in.mp4", "out.jpg", duration_s=3.0, frame_count=3)
    vf = _get_vf(cmd)
    assert "tile=3x1" in vf


def test_build_filmstrip_command_quality_flag() -> None:
    """Command must include -q:v for JPEG quality control."""
    cmd = build_filmstrip_command("in.mp4", "out.jpg", duration_s=10.0, frame_count=10)
    assert "-q:v" in cmd


# ---------------------------------------------------------------------------
# generate_filmstrip (None / zero duration guard)
# ---------------------------------------------------------------------------


async def test_generate_filmstrip_none_duration_no_division_by_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """generate_filmstrip with duration_s=None must use effective_duration=1.0.

    Verifies that the fps filter denominator is 1.0 (not 0 or None) and the
    tile is 1x1, confirming no zero-division and a well-formed command.
    """
    captured: list[list[str]] = []

    async def fake_run_ffmpeg(cmd: list[str]) -> None:
        captured.append(cmd)

    monkeypatch.setattr("app.media.filmstrip.run_ffmpeg", fake_run_ffmpeg)

    await generate_filmstrip("in.mp4", "out.jpg", duration_s=None)

    assert len(captured) == 1
    cmd = captured[0]
    vf = _get_vf(cmd)
    # frame_count=1, effective_duration=1.0 → fps=1/1.0, tile=1x1
    assert "fps=1/1.0" in vf
    assert "tile=1x1" in vf


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _get_vf(cmd: list[str]) -> str:
    """Extract the -vf argument value from a command list."""
    idx = cmd.index("-vf")
    return cmd[idx + 1]
