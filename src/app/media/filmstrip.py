"""Filmstrip sprite generation: extract N frames and tile them into a JPEG."""

import math

from app.media.ffmpeg import run_ffmpeg


def compute_frame_count(duration_s: float | None) -> int:
    """Return the number of frames to include in the filmstrip.

    Uses up to 10 frames for normal-length clips.  For clips shorter than
    10 seconds, the count is capped to ``floor(duration_s)`` so that we never
    sample the same frame twice.  The result is always at least 1.
    """
    if duration_s is None or duration_s <= 0:
        return 1
    return max(1, min(10, math.floor(duration_s)))


def build_filmstrip_command(
    src: str,
    dst: str,
    *,
    duration_s: float,
    frame_count: int,
) -> list[str]:
    """Return the ffmpeg arg list that produces a tiled filmstrip JPEG.

    The output is a single JPEG with ``frame_count`` thumbnails (each 72 px tall,
    width proportional to the source) laid out horizontally.
    """
    fps_filter = f"fps={frame_count}/{duration_s}"
    vf = f"{fps_filter},scale=-1:72,tile={frame_count}x1"
    return [
        "ffmpeg",
        "-i",
        src,
        "-vf",
        vf,
        "-frames:v",
        "1",
        "-q:v",
        "3",
        "-y",
        dst,
    ]


async def generate_filmstrip(
    src: str,
    dst: str,
    *,
    duration_s: float | None,
) -> None:
    """Generate a filmstrip sprite JPEG from *src* and write it to *dst*.

    ``duration_s`` is the clip duration in seconds; used to compute the number
    of frames.  Falls back to a single frame if the duration is unknown.
    """
    effective_duration = duration_s if duration_s and duration_s > 0 else 1.0
    frame_count = compute_frame_count(effective_duration)
    cmd = build_filmstrip_command(
        src, dst, duration_s=effective_duration, frame_count=frame_count
    )
    await run_ffmpeg(cmd)
