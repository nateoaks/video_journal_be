"""Unit tests for the shared Range-aware media response builder."""

from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from app.common.exceptions import AppError, RangeNotSatisfiableError
from app.common.media_response import _parse_range_header, build_media_response
from app.core.exception_handlers import app_error_handler

# ---------------------------------------------------------------------------
# _parse_range_header unit tests (pure function)
# ---------------------------------------------------------------------------


def test_full_range_bytes_0_99() -> None:
    """bytes=0-99 → (0, 99)."""
    assert _parse_range_header("bytes=0-99", 1000) == (0, 99)


def test_open_ended_range() -> None:
    """bytes=500- → (500, file_size - 1)."""
    assert _parse_range_header("bytes=500-", 1000) == (500, 999)


def test_suffix_range() -> None:
    """bytes=-200 → last 200 bytes."""
    assert _parse_range_header("bytes=-200", 1000) == (800, 999)


def test_suffix_range_larger_than_file() -> None:
    """bytes=-2000 on a 1000-byte file → (0, 999) — clamped to whole file."""
    assert _parse_range_header("bytes=-2000", 1000) == (0, 999)


def test_out_of_bounds_range_raises_416() -> None:
    """start >= file_size → RangeNotSatisfiableError."""
    with pytest.raises(RangeNotSatisfiableError):
        _parse_range_header("bytes=1000-1099", 1000)


def test_malformed_range_raises_416() -> None:
    """Non-bytes= prefix → RangeNotSatisfiableError."""
    with pytest.raises(RangeNotSatisfiableError):
        _parse_range_header("invalid", 1000)


def test_malformed_range_no_bytes_prefix_raises_416() -> None:
    """Range without 'bytes=' → RangeNotSatisfiableError."""
    with pytest.raises(RangeNotSatisfiableError):
        _parse_range_header("0-99", 100)


def test_range_end_clamped_to_file_size() -> None:
    """end > file_size - 1 is clamped to file_size - 1."""
    assert _parse_range_header("bytes=0-9999", 100) == (0, 99)


# ---------------------------------------------------------------------------
# build_media_response integration tests via a minimal ASGI app
# ---------------------------------------------------------------------------

_CONTENT = b"Hello, world! This is test content for range requests." * 10  # ~540 bytes
_CONTENT_LEN = len(_CONTENT)


def _make_app(tmp_path: Path) -> FastAPI:
    """Build a minimal FastAPI app serving a test file via build_media_response."""
    test_file = tmp_path / "test.mp4"
    test_file.write_bytes(_CONTENT)

    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]

    @app.get("/media")
    async def serve(request: Request) -> object:
        return await build_media_response(str(test_file), "video/mp4", request)

    return app


async def test_no_range_returns_200(tmp_path: Path) -> None:
    """No Range header → 200 with Accept-Ranges and correct Content-Length."""
    app = _make_app(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/media")

    assert response.status_code == 200
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-length"] == str(_CONTENT_LEN)
    assert response.content == _CONTENT


async def test_range_0_to_99_returns_206(tmp_path: Path) -> None:
    """bytes=0-99 → 206 with correct Content-Range and first 100 bytes."""
    app = _make_app(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/media", headers={"Range": "bytes=0-99"})

    assert response.status_code == 206
    assert response.headers["content-range"] == f"bytes 0-99/{_CONTENT_LEN}"
    assert response.headers["content-length"] == "100"
    assert response.content == _CONTENT[:100]


async def test_open_ended_range_returns_206(tmp_path: Path) -> None:
    """bytes=500- → 206 from byte 500 to end."""
    app = _make_app(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/media", headers={"Range": "bytes=500-"})

    assert response.status_code == 206
    expected_end = _CONTENT_LEN - 1
    expected_len = _CONTENT_LEN - 500
    assert (
        response.headers["content-range"] == f"bytes 500-{expected_end}/{_CONTENT_LEN}"
    )
    assert response.headers["content-length"] == str(expected_len)
    assert response.content == _CONTENT[500:]


async def test_suffix_range_returns_206(tmp_path: Path) -> None:
    """bytes=-200 → 206 with last 200 bytes."""
    app = _make_app(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/media", headers={"Range": "bytes=-200"})

    assert response.status_code == 206
    expected_start = _CONTENT_LEN - 200
    expected_end = _CONTENT_LEN - 1
    assert (
        response.headers["content-range"]
        == f"bytes {expected_start}-{expected_end}/{_CONTENT_LEN}"
    )
    assert response.content == _CONTENT[-200:]


async def test_out_of_bounds_range_returns_416(tmp_path: Path) -> None:
    """Range beyond file size → 416."""
    app = _make_app(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/media", headers={"Range": f"bytes={_CONTENT_LEN}-{_CONTENT_LEN + 100}"}
        )

    assert response.status_code == 416


async def test_malformed_range_returns_416(tmp_path: Path) -> None:
    """Malformed Range header → 416."""
    app = _make_app(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/media", headers={"Range": "not-a-range"})

    assert response.status_code == 416


async def test_zero_byte_file_returns_200(tmp_path: Path) -> None:
    """Zero-byte file → 200 with Content-Length: 0."""
    empty_file = tmp_path / "empty.mp4"
    empty_file.write_bytes(b"")

    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]

    @app.get("/empty")
    async def serve_empty(request: Request) -> object:
        return await build_media_response(str(empty_file), "video/mp4", request)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/empty")

    assert response.status_code == 200
    assert response.headers["content-length"] == "0"
    assert response.content == b""


async def test_accept_ranges_header_present_on_200(tmp_path: Path) -> None:
    """Accept-Ranges: bytes must appear on 200 responses."""
    app = _make_app(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/media")

    assert response.headers.get("accept-ranges") == "bytes"


async def test_cache_control_default_no_cache(tmp_path: Path) -> None:
    """Default cache_control is no-cache."""
    app = _make_app(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/media")

    assert response.headers.get("cache-control") == "no-cache"


async def test_zero_byte_file_suffix_range_returns_200(tmp_path: Path) -> None:
    """Zero-byte file + suffix range (bytes=-200) → 200 with Content-Length: 0.

    The suffix-range parser returns (0, -1) for an empty file, and the caller
    falls through to the zero-byte early-return path which yields a 200 FileResponse.
    """
    empty_file = tmp_path / "empty2.mp4"
    empty_file.write_bytes(b"")

    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]

    @app.get("/empty-suffix")
    async def serve_empty_suffix(request: Request) -> object:
        return await build_media_response(str(empty_file), "video/mp4", request)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/empty-suffix", headers={"Range": "bytes=-200"})

    assert response.status_code == 200
    assert response.headers["content-length"] == "0"
    assert response.content == b""


async def test_zero_byte_file_explicit_range_returns_416(tmp_path: Path) -> None:
    """Zero-byte file + explicit range (bytes=0-99) → 416.

    An explicit start=0 on an empty file hits the file_size==0 guard in
    _parse_range_header and raises RangeNotSatisfiableError.
    """
    empty_file = tmp_path / "empty3.mp4"
    empty_file.write_bytes(b"")

    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]

    @app.get("/empty-explicit")
    async def serve_empty_explicit(request: Request) -> object:
        return await build_media_response(str(empty_file), "video/mp4", request)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/empty-explicit", headers={"Range": "bytes=0-99"})

    assert response.status_code == 416


async def test_cache_control_custom(tmp_path: Path) -> None:
    """Custom cache_control is forwarded to the response."""
    test_file = tmp_path / "v.mp4"
    test_file.write_bytes(_CONTENT)

    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]

    @app.get("/immutable")
    async def serve_immutable(request: Request) -> object:
        return await build_media_response(
            str(test_file),
            "video/mp4",
            request,
            cache_control="public, max-age=31536000, immutable",
        )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/immutable")

    assert (
        response.headers.get("cache-control") == "public, max-age=31536000, immutable"
    )
