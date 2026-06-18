"""FFmpeg subprocess wrapper for video transcoding."""

import subprocess

import anyio

from app.common.exceptions import AppError
from app.core.config import get_settings


class FfmpegError(AppError):
    """Raised when ffmpeg fails or times out."""

    status_code = 422
    message = "FFmpeg processing failed"


def _run_ffmpeg_sync(args: list[str], timeout: int) -> None:
    """Run ffmpeg synchronously; called via anyio.to_thread.run_sync."""
    try:
        subprocess.run(  # noqa: S603
            args,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.CalledProcessError as exc:
        raise FfmpegError(exc.stderr) from exc
    except subprocess.TimeoutExpired as exc:
        raise FfmpegError("ffmpeg timed out") from exc


async def run_ffmpeg(args: list[str]) -> None:
    """Run ffmpeg asynchronously, offloading to a thread.

    Reads the timeout from Settings.normalize_timeout_s.
    Raises FfmpegError on non-zero exit or timeout.
    """
    timeout = get_settings().normalize_timeout_s
    await anyio.to_thread.run_sync(lambda: _run_ffmpeg_sync(args, timeout))
