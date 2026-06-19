"""Shared Range-aware HTTP response builder for local media files."""

import os
from collections.abc import AsyncIterator
from pathlib import Path

import anyio
import anyio.to_thread
from fastapi import Request
from fastapi.responses import Response, StreamingResponse
from starlette.responses import FileResponse

from app.common.exceptions import RangeNotSatisfiableError

CACHE_IMMUTABLE = "public, max-age=31536000, immutable"

_CHUNK_SIZE = 64 * 1024  # 64 KiB
_MAX_RANGE_HEADER_LEN = 64


def _parse_range_header(header: str, file_size: int) -> tuple[int, int]:
    """Parse a single ``bytes=N-M`` Range header into inclusive (start, end) offsets.

    Supports full (``0-99``), open-ended (``500-``), and suffix (``-200``) forms.
    Raises RangeNotSatisfiableError for malformed or unsatisfiable ranges.
    """
    if len(header) > _MAX_RANGE_HEADER_LEN:
        raise RangeNotSatisfiableError("Range header too long")

    if not header.startswith("bytes="):
        raise RangeNotSatisfiableError("Invalid Range header format")

    range_spec = header[len("bytes=") :]
    parts = range_spec.split("-", 1)
    if len(parts) != 2:
        raise RangeNotSatisfiableError("Invalid Range header format")

    start_str, end_str = parts[0].strip(), parts[1].strip()

    # Suffix-range: bytes=-N means last N bytes.
    if not start_str:
        try:
            suffix_len = int(end_str)
        except ValueError as exc:
            raise RangeNotSatisfiableError("Invalid Range suffix value") from exc
        if file_size == 0:
            return 0, -1  # empty file — caller handles this
        start = max(0, file_size - suffix_len)
        end = file_size - 1
        return start, end

    try:
        start = int(start_str)
    except ValueError as exc:
        raise RangeNotSatisfiableError("Invalid Range start value") from exc

    if end_str == "":
        end = file_size - 1
    else:
        try:
            end = int(end_str)
        except ValueError as exc:
            raise RangeNotSatisfiableError("Invalid Range end value") from exc

    if file_size == 0 or start < 0 or end < start or start >= file_size:
        raise RangeNotSatisfiableError("Range not satisfiable")

    # Clamp end to last valid byte.
    end = min(end, file_size - 1)
    return start, end


async def _stream_range(path: str, start: int, end: int) -> AsyncIterator[bytes]:
    """Yield bytes [start, end] inclusive from path in chunks."""
    async with await anyio.open_file(path, "rb") as f:
        await f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = await f.read(min(_CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


async def build_media_response(
    storage_key: str,
    content_type: str,
    request: Request,
    *,
    cache_control: str = "no-cache",
) -> Response:
    """Build a Range-aware HTTP response for a local media file.

    Returns a FileResponse (200) when no Range header is present, or a 206
    partial StreamingResponse when a valid Range header is supplied.  Always sets
    ``Accept-Ranges: bytes``, ``Content-Type``, ``Content-Length``, and
    ``Cache-Control``.  Raises RangeNotSatisfiableError (416) for invalid ranges.

    The ``storage_key`` must be a local filesystem path (as returned by
    ``StorageBackend.path_or_url``).
    """
    local_path = storage_key
    stat_result: os.stat_result = await anyio.to_thread.run_sync(
        lambda: Path(local_path).stat()
    )
    file_size = stat_result.st_size

    range_header = request.headers.get("range")

    common_headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": cache_control,
    }

    if range_header is None:
        return FileResponse(
            local_path,
            media_type=content_type,
            stat_result=stat_result,
            headers=common_headers,
        )

    start, end = _parse_range_header(range_header, file_size)

    # Handle zero-byte file with suffix-range that collapses to empty.
    # Return a plain Response rather than FileResponse so that Starlette's
    # built-in Range processing does not see the Range header and emit 416.
    if file_size == 0:
        return Response(
            content=b"",
            media_type=content_type,
            headers={**common_headers, "Content-Length": "0"},
        )

    content_length = end - start + 1
    return StreamingResponse(
        _stream_range(local_path, start, end),
        status_code=206,
        headers={
            **common_headers,
            "Content-Type": content_type,
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(content_length),
        },
    )
