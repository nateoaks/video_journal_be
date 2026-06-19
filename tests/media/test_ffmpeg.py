"""Unit tests for app.media.ffmpeg — subprocess is fully stubbed."""

import subprocess
from subprocess import CompletedProcess

import pytest

from app.media.ffmpeg import FfmpegError, run_ffmpeg


async def test_run_ffmpeg_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """ffmpeg exits 0 → run_ffmpeg completes without error."""

    def fake_run(args: object, **kwargs: object) -> CompletedProcess[str]:
        return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    await run_ffmpeg(["ffmpeg", "-version"])  # must not raise


async def test_run_ffmpeg_nonzero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    """ffmpeg exits non-zero → FfmpegError raised containing stderr text."""

    def fake_run(args: object, **kwargs: object) -> CompletedProcess[str]:
        raise subprocess.CalledProcessError(returncode=1, cmd=args, stderr="some error")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(FfmpegError, match="some error"):
        await run_ffmpeg(["ffmpeg", "-i", "in.mp4", "out.mp4"])


async def test_run_ffmpeg_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Subprocess timeout → FfmpegError raised."""

    def fake_run(args: object, **kwargs: object) -> CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=[], timeout=300)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(FfmpegError, match="timed out"):
        await run_ffmpeg(["ffmpeg", "-i", "in.mp4", "out.mp4"])
