"""ffprobe wrapper for extracting video metadata."""

import contextlib
import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import anyio

from app.common.exceptions import AppError


class FfprobeError(AppError):
    """Raised when ffprobe fails or returns unexpected output."""

    status_code = 422
    message = "Failed to probe video file"


@dataclass(frozen=True)
class ProbeResult:
    """Parsed metadata extracted from a video file via ffprobe."""

    duration_s: float | None
    width: int | None
    height: int | None
    codec_name: str | None
    recorded_at: datetime | None


def _run_ffprobe(path: str) -> bytes:
    """Run ffprobe synchronously; called via anyio.to_thread.run_sync."""
    try:
        result = subprocess.run(  # noqa: S603
            [  # noqa: S607
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                path,
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
    except subprocess.CalledProcessError as exc:
        raise FfprobeError(
            f"ffprobe exited with code {exc.returncode}: {exc.stderr.decode(errors='replace')}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise FfprobeError("ffprobe timed out") from exc
    return result.stdout


def _parse_rotation(stream: dict[str, object]) -> int:
    """Extract display rotation from a stream dict, normalised to 0/90/180/270."""
    # Modern ffprobe encodes rotation in side_data_list as a Display Matrix entry.
    side_data_list = stream.get("side_data_list")
    if isinstance(side_data_list, list):
        for entry in side_data_list:
            if (
                isinstance(entry, dict)
                and entry.get("side_data_type") == "Display Matrix"
            ):
                raw = entry.get("rotation")
                if raw is not None:
                    return abs(int(float(str(raw)))) % 360

    # Fallback: older ffprobe stores rotation in stream tags.
    tags = stream.get("tags")
    if isinstance(tags, dict):
        raw_tag = tags.get("rotate")
        if raw_tag is not None:
            return abs(int(float(str(raw_tag)))) % 360

    return 0


def _parse_recorded_at(
    fmt: dict[str, object], stream: dict[str, object]
) -> datetime | None:
    """Extract creation timestamp, returning a UTC-aware datetime or None."""
    fmt_tags: dict[str, object] = {}
    raw_fmt_tags = fmt.get("tags")
    if isinstance(raw_fmt_tags, dict):
        fmt_tags = raw_fmt_tags

    stream_tags: dict[str, object] = {}
    raw_stream_tags = stream.get("tags")
    if isinstance(raw_stream_tags, dict):
        stream_tags = raw_stream_tags

    candidates = [
        fmt_tags.get("com.apple.quicktime.creationdate"),
        fmt_tags.get("creation_time"),
        stream_tags.get("creation_time"),
    ]

    for candidate in candidates:
        if candidate is None:
            continue
        raw_str = str(candidate)
        try:
            dt = datetime.fromisoformat(raw_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except ValueError:
            continue

    return None


def _parse_output(raw: bytes) -> ProbeResult:
    """Parse raw ffprobe JSON output into a ProbeResult."""
    try:
        data: dict[str, object] = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FfprobeError(f"ffprobe produced invalid JSON: {exc}") from exc

    streams = data.get("streams")
    if not isinstance(streams, list):
        raise FfprobeError("ffprobe output missing 'streams' key")

    video_stream: dict[str, object] | None = None
    for s in streams:
        if isinstance(s, dict) and s.get("codec_type") == "video":
            video_stream = s
            break

    if video_stream is None:
        raise FfprobeError("No video stream found in file")

    fmt = data.get("format")
    if not isinstance(fmt, dict):
        fmt = {}

    # Duration from format section.
    duration_s: float | None = None
    raw_duration = fmt.get("duration")
    if raw_duration is not None:
        with contextlib.suppress(ValueError):
            duration_s = float(str(raw_duration))

    # Width and height, accounting for rotation.
    raw_width = video_stream.get("width")
    raw_height = video_stream.get("height")
    width: int | None = int(str(raw_width)) if raw_width is not None else None
    height: int | None = int(str(raw_height)) if raw_height is not None else None

    rotation = _parse_rotation(video_stream)
    if rotation in {90, 270} and width is not None and height is not None:
        width, height = height, width

    codec_name: str | None = None
    raw_codec = video_stream.get("codec_name")
    if raw_codec is not None:
        codec_name = str(raw_codec)

    recorded_at = _parse_recorded_at(fmt, video_stream)

    return ProbeResult(
        duration_s=duration_s,
        width=width,
        height=height,
        codec_name=codec_name,
        recorded_at=recorded_at,
    )


async def probe(path: str | Path) -> ProbeResult:
    """Probe a video file and return extracted metadata.

    Runs ffprobe in a thread to avoid blocking the event loop.
    Raises FfprobeError on any failure.
    """
    path_str = str(path)
    raw = await anyio.to_thread.run_sync(lambda: _run_ffprobe(path_str))
    return _parse_output(raw)
