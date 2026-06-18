"""Unit tests for app.media.ffprobe — ffprobe output is fully stubbed."""

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from app.media.ffprobe import FfprobeError, ProbeResult, probe


def _make_ffprobe_output(
    *,
    codec_type: str = "video",
    codec_name: str = "h264",
    width: int = 1920,
    height: int = 1080,
    duration: str = "10.5",
    side_data_list: list[dict[str, object]] | None = None,
    stream_tags: dict[str, object] | None = None,
    format_tags: dict[str, object] | None = None,
) -> bytes:
    """Build a minimal ffprobe JSON payload."""
    stream: dict[str, object] = {
        "codec_type": codec_type,
        "codec_name": codec_name,
        "width": width,
        "height": height,
    }
    if side_data_list is not None:
        stream["side_data_list"] = side_data_list
    if stream_tags is not None:
        stream["tags"] = stream_tags

    fmt: dict[str, object] = {"duration": duration}
    if format_tags is not None:
        fmt["tags"] = format_tags

    return json.dumps({"streams": [stream], "format": fmt}).encode()


# ---------------------------------------------------------------------------
# Helpers to set up the monkeypatch
# ---------------------------------------------------------------------------


def _patch_run(monkeypatch: pytest.MonkeyPatch, stdout: bytes) -> None:
    """Make subprocess.run return successfully with the given stdout."""

    def fake_run(args: object, **kwargs: object) -> CompletedProcess[bytes]:
        return CompletedProcess(args=args, returncode=0, stdout=stdout, stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)


def _patch_run_error(
    monkeypatch: pytest.MonkeyPatch, returncode: int = 1, stderr: bytes = b"error"
) -> None:
    """Make subprocess.run raise CalledProcessError."""

    def fake_run(args: object, **kwargs: object) -> CompletedProcess[bytes]:
        exc = subprocess.CalledProcessError(returncode, args, stderr=stderr)
        raise exc

    monkeypatch.setattr(subprocess, "run", fake_run)


def _patch_run_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make subprocess.run raise TimeoutExpired."""

    def fake_run(args: object, **kwargs: object) -> CompletedProcess[bytes]:
        raise subprocess.TimeoutExpired(cmd=args, timeout=30)

    monkeypatch.setattr(subprocess, "run", fake_run)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_portrait_iphone_clip_display_matrix_rotation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Portrait iPhone clip: Display Matrix -90 rotation swaps width and height."""
    raw_output = _make_ffprobe_output(
        width=1920,
        height=1080,
        side_data_list=[{"side_data_type": "Display Matrix", "rotation": -90}],
        format_tags={"com.apple.quicktime.creationdate": "2024-03-15T10:30:00+00:00"},
    )
    _patch_run(monkeypatch, raw_output)

    result = await probe(Path("/fake/video.mov"))

    assert isinstance(result, ProbeResult)
    # -90 degrees → abs(-90) % 360 = 90 → swap
    assert result.width == 1080
    assert result.height == 1920
    assert result.recorded_at == datetime(2024, 3, 15, 10, 30, 0, tzinfo=UTC)
    assert result.duration_s == pytest.approx(10.5)
    assert result.codec_name == "h264"


async def test_creation_time_from_format_tags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """H.264 clip with only creation_time in format tags → correct recorded_at."""
    raw_output = _make_ffprobe_output(
        codec_name="h264",
        format_tags={"creation_time": "2023-06-01T08:00:00Z"},
    )
    _patch_run(monkeypatch, raw_output)

    result = await probe(Path("/fake/video.mp4"))

    assert result.recorded_at == datetime(2023, 6, 1, 8, 0, 0, tzinfo=UTC)
    # No rotation → dimensions unchanged
    assert result.width == 1920
    assert result.height == 1080


async def test_no_creation_tag_returns_none_recorded_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When no creation tags are present, recorded_at is None."""
    raw_output = _make_ffprobe_output()
    _patch_run(monkeypatch, raw_output)

    result = await probe(Path("/fake/video.mp4"))

    assert result.recorded_at is None


async def test_nonzero_exit_code_raises_ffprobe_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-zero ffprobe exit raises FfprobeError."""
    _patch_run_error(monkeypatch, returncode=1)

    with pytest.raises(FfprobeError):
        await probe(Path("/fake/video.mp4"))


async def test_timeout_raises_ffprobe_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Timeout during ffprobe execution raises FfprobeError."""
    _patch_run_timeout(monkeypatch)

    with pytest.raises(FfprobeError):
        await probe(Path("/fake/video.mp4"))


async def test_json_parse_failure_raises_ffprobe_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid JSON output from ffprobe raises FfprobeError."""
    _patch_run(monkeypatch, b"not valid json {{{")

    with pytest.raises(FfprobeError):
        await probe(Path("/fake/video.mp4"))


async def test_no_video_stream_raises_ffprobe_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ffprobe output with no video stream raises FfprobeError."""
    output = json.dumps(
        {
            "streams": [{"codec_type": "audio", "codec_name": "aac"}],
            "format": {"duration": "5.0"},
        }
    ).encode()
    _patch_run(monkeypatch, output)

    with pytest.raises(FfprobeError, match="No video stream"):
        await probe(Path("/fake/audio.mp4"))


async def test_stream_tag_rotation_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rotation stored in stream tags (legacy path) also swaps dimensions."""
    raw_output = _make_ffprobe_output(
        width=1920,
        height=1080,
        stream_tags={"rotate": "90"},
    )
    _patch_run(monkeypatch, raw_output)

    result = await probe(Path("/fake/video.mp4"))

    assert result.width == 1080
    assert result.height == 1920


async def test_180_rotation_does_not_swap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """180° rotation does not swap width and height."""
    raw_output = _make_ffprobe_output(
        width=1920,
        height=1080,
        side_data_list=[{"side_data_type": "Display Matrix", "rotation": 180}],
    )
    _patch_run(monkeypatch, raw_output)

    result = await probe(Path("/fake/video.mp4"))

    assert result.width == 1920
    assert result.height == 1080
