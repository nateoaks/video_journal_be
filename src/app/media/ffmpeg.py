"""FFmpeg subprocess wrapper for video transcoding."""

import contextlib
import subprocess
import threading
from collections.abc import Callable

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


_STDERR_TAIL_LINES = 20


def _run_ffmpeg_with_progress_sync(
    args: list[str],
    timeout: int,
    on_progress: Callable[[int], None] | None = None,
) -> None:
    """Run ffmpeg with -progress pipe:1; stream stdout for progress callbacks.

    Drains stderr in a background thread to prevent pipe deadlock.  Parses
    ``out_time_us=<n>`` lines from stdout and calls ``on_progress(n)`` when set.
    Raises FfmpegError on non-zero exit or timeout.
    """
    proc = subprocess.Popen(  # noqa: S603
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    stderr_lines: list[str] = []

    def _drain_stderr() -> None:
        if proc.stderr is None:
            return
        for line in proc.stderr:
            stderr_lines.append(line)

    stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
    stderr_thread.start()

    try:
        if proc.stdout is not None:
            for line in proc.stdout:
                stripped = line.strip()
                if stripped.startswith("out_time_us=") and on_progress is not None:
                    raw = stripped[len("out_time_us=") :]
                    with contextlib.suppress(ValueError):
                        on_progress(int(raw))
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        proc.kill()
        proc.wait()
        raise FfmpegError("ffmpeg timed out") from exc
    finally:
        stderr_thread.join()

    if proc.returncode != 0:
        tail = "\n".join(stderr_lines[-_STDERR_TAIL_LINES:])
        raise FfmpegError(tail)


async def run_ffmpeg_with_progress(
    args: list[str],
    on_progress: Callable[[int], None] | None = None,
) -> None:
    """Run ffmpeg with progress reporting, offloading to a thread.

    Expects -progress pipe:1 in args.  Calls on_progress(out_time_us) for each
    parsed progress line.  On failure, raises FfmpegError with the last 20 lines
    of stderr as the message.
    """
    timeout = get_settings().normalize_timeout_s
    await anyio.to_thread.run_sync(
        lambda: _run_ffmpeg_with_progress_sync(args, timeout, on_progress)
    )
