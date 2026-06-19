"""Unit tests for _run_ffmpeg_with_progress_sync progress parsing."""

import subprocess
from io import StringIO
from unittest.mock import MagicMock

import pytest

from app.media.ffmpeg import FfmpegError, _run_ffmpeg_with_progress_sync


def _make_fake_proc(
    stdout_text: str,
    stderr_text: str = "",
    returncode: int = 0,
) -> MagicMock:
    """Build a fake Popen-style object whose stdout/stderr are StringIO streams."""
    proc = MagicMock()
    proc.stdout = StringIO(stdout_text)
    proc.stderr = StringIO(stderr_text)
    proc.returncode = returncode
    proc.wait.return_value = returncode
    proc.kill.return_value = None
    return proc


def test_on_progress_called_with_parsed_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """on_progress receives the integer value from each out_time_us= line."""
    stdout = "out_time_us=1000000\nout_time_us=2000000\nprogress=end\n"
    fake_proc = _make_fake_proc(stdout_text=stdout)

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: fake_proc)

    received: list[int] = []
    _run_ffmpeg_with_progress_sync(["ffmpeg"], timeout=60, on_progress=received.append)

    assert received == [1_000_000, 2_000_000]


def test_no_callback_no_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """on_progress=None is accepted; the function completes without error."""
    stdout = "out_time_us=500000\nprogress=end\n"
    fake_proc = _make_fake_proc(stdout_text=stdout)

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: fake_proc)

    # Must not raise even though there's no callback.
    _run_ffmpeg_with_progress_sync(["ffmpeg"], timeout=60, on_progress=None)


def test_nonzero_exit_raises_ffmpeg_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-zero exit code raises FfmpegError containing stderr tail."""
    stderr = "error line 1\nerror line 2\n"
    fake_proc = _make_fake_proc(stdout_text="", stderr_text=stderr, returncode=1)

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: fake_proc)

    with pytest.raises(FfmpegError, match="error line"):
        _run_ffmpeg_with_progress_sync(["ffmpeg"], timeout=60)


def test_timeout_raises_ffmpeg_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """TimeoutExpired from proc.wait(timeout=...) raises FfmpegError('ffmpeg timed out')."""
    fake_proc = _make_fake_proc(stdout_text="")

    # Only raise on the first call (the timed wait); bare wait() after kill() succeeds.
    call_count = 0

    def _wait_side_effect(**kwargs: object) -> int:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise subprocess.TimeoutExpired(cmd=["ffmpeg"], timeout=1)
        return 0

    fake_proc.wait.side_effect = _wait_side_effect

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: fake_proc)

    with pytest.raises(FfmpegError, match="timed out"):
        _run_ffmpeg_with_progress_sync(["ffmpeg"], timeout=1)


def test_invalid_out_time_us_value_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-integer out_time_us value is silently skipped."""
    stdout = "out_time_us=N/A\nout_time_us=3000000\n"
    fake_proc = _make_fake_proc(stdout_text=stdout)

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: fake_proc)

    received: list[int] = []
    _run_ffmpeg_with_progress_sync(["ffmpeg"], timeout=60, on_progress=received.append)

    assert received == [3_000_000]
