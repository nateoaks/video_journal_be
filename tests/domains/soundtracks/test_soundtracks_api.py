"""Tests for the soundtracks API endpoints."""

from pathlib import Path
from typing import Any

import anyio.to_thread
import pytest
from httpx import AsyncClient

import app.domains.soundtracks.service as soundtracks_service_module
from app.domains.soundtracks.models import Soundtrack
from app.media.ffprobe import AudioProbeResult, FfprobeError
from app.storage.local import LocalStorage

# A minimal fake payload — content doesn't matter; probe is stubbed.
_FAKE_MP3 = b"ID3" + b"\x00" * 100
_FAKE_M4A = b"\x00\x00\x00\x20ftyp" + b"\x00" * 100

_GOOD_PROBE = AudioProbeResult(duration_s=180.0, title="Test Track")
_PROBE_NO_TITLE = AudioProbeResult(duration_s=120.0, title=None)


def _stub_probe_audio(result: AudioProbeResult | Exception) -> Any:
    """Return an async callable that returns result or raises it."""
    if isinstance(result, Exception):
        exc = result

        async def _raise(_path: str | Path) -> AudioProbeResult:
            raise exc

        return _raise
    else:
        probe_result = result

        async def _return(_path: str | Path) -> AudioProbeResult:
            return probe_result

        return _return


# ---------------------------------------------------------------------------
# Unit tests — pure helpers
# ---------------------------------------------------------------------------


def test_safe_extension_allowed_extensions() -> None:
    """Each allowed audio extension passes validation."""
    from app.domains.soundtracks.utils import safe_extension

    for ext in (".mp3", ".m4a", ".aac", ".wav", ".flac"):
        assert safe_extension(f"track{ext}") == ext


def test_safe_extension_uppercase_normalised() -> None:
    """Uppercase extensions are lowercased and accepted."""
    from app.domains.soundtracks.utils import safe_extension

    assert safe_extension("TRACK.MP3") == ".mp3"


def test_safe_extension_unsupported_raises_415() -> None:
    """.ogg is not allowed → UnsupportedMediaTypeError(415)."""
    from app.common.exceptions import UnsupportedMediaTypeError
    from app.domains.soundtracks.utils import safe_extension

    with pytest.raises(UnsupportedMediaTypeError) as exc_info:
        safe_extension("track.ogg")
    assert exc_info.value.status_code == 415


def test_safe_extension_no_extension_raises_415() -> None:
    """File with no extension → UnsupportedMediaTypeError(415)."""
    from app.common.exceptions import UnsupportedMediaTypeError
    from app.domains.soundtracks.utils import safe_extension

    with pytest.raises(UnsupportedMediaTypeError) as exc_info:
        safe_extension("tracknoext")
    assert exc_info.value.status_code == 415


def test_title_from_filename_strips_extension() -> None:
    """title_from_filename returns the stem."""
    from app.domains.soundtracks.utils import title_from_filename

    assert title_from_filename("my song.mp3") == "my song"
    assert title_from_filename("track.01.flac") == "track.01"


# ---------------------------------------------------------------------------
# POST /api/v1/soundtracks
# ---------------------------------------------------------------------------


async def test_upload_mp3_returns_201(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Valid .mp3 upload → 201, body contains expected fields."""
    monkeypatch.setattr(
        soundtracks_service_module, "probe_audio", _stub_probe_audio(_GOOD_PROBE)
    )

    response = await client.post(
        "/api/v1/soundtracks",
        files={"file": ("track.mp3", _FAKE_MP3, "audio/mpeg")},
    )

    assert response.status_code == 201
    body = response.json()
    assert "id" in body
    assert body["title"] == "Test Track"
    assert body["duration_s"] == pytest.approx(180.0)
    assert "key" in body
    assert "uploaded_at" in body


async def test_upload_m4a_returns_201(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Valid .m4a upload → 201 with correct metadata."""
    monkeypatch.setattr(
        soundtracks_service_module, "probe_audio", _stub_probe_audio(_GOOD_PROBE)
    )

    response = await client.post(
        "/api/v1/soundtracks",
        files={"file": ("track.m4a", _FAKE_M4A, "audio/mp4")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Test Track"
    assert body["duration_s"] == pytest.approx(180.0)


async def test_upload_title_falls_back_to_filename_stem(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When probe_audio returns title=None, title falls back to filename stem."""
    monkeypatch.setattr(
        soundtracks_service_module, "probe_audio", _stub_probe_audio(_PROBE_NO_TITLE)
    )

    response = await client.post(
        "/api/v1/soundtracks",
        files={"file": ("my_awesome_track.mp3", _FAKE_MP3, "audio/mpeg")},
    )

    assert response.status_code == 201
    assert response.json()["title"] == "my_awesome_track"


async def test_upload_unsupported_extension_returns_415(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unsupported .ogg extension → 415 before any DB row is created."""
    monkeypatch.setattr(
        soundtracks_service_module, "probe_audio", _stub_probe_audio(_GOOD_PROBE)
    )

    response = await client.post(
        "/api/v1/soundtracks",
        files={"file": ("track.ogg", _FAKE_MP3, "audio/ogg")},
    )

    assert response.status_code == 415

    list_response = await client.get("/api/v1/soundtracks")
    assert list_response.json() == []


async def test_upload_ffprobe_failure_returns_422_no_db_row_no_file(
    client: AsyncClient,
    storage: LocalStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When probe_audio fails the file is cleaned up and 422 is returned."""
    monkeypatch.setattr(
        soundtracks_service_module,
        "probe_audio",
        _stub_probe_audio(FfprobeError("bad audio")),
    )

    response = await client.post(
        "/api/v1/soundtracks",
        files={"file": ("broken.mp3", _FAKE_MP3, "audio/mpeg")},
    )

    assert response.status_code == 422

    list_response = await client.get("/api/v1/soundtracks")
    assert list_response.json() == []

    media_dir = storage._base_dir
    stored_files = (
        [p for p in media_dir.rglob("*") if p.is_file()] if media_dir.exists() else []
    )
    assert stored_files == [], f"Expected no files in storage, found: {stored_files}"


async def test_upload_exceeds_size_limit_returns_413(
    client: AsyncClient,
    storage: LocalStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Upload exceeding max_upload_bytes → 413, no DB row, no file in storage."""
    monkeypatch.setattr(
        soundtracks_service_module, "probe_audio", _stub_probe_audio(_GOOD_PROBE)
    )

    from app.core.config import Settings

    monkeypatch.setattr(
        soundtracks_service_module,
        "get_settings",
        lambda: Settings(max_upload_bytes=10),
    )

    response = await client.post(
        "/api/v1/soundtracks",
        files={"file": ("big.mp3", _FAKE_MP3, "audio/mpeg")},
    )

    assert response.status_code == 413

    list_response = await client.get("/api/v1/soundtracks")
    assert list_response.json() == []

    media_dir = storage._base_dir
    stored_files = (
        [p for p in media_dir.rglob("*") if p.is_file()] if media_dir.exists() else []
    )
    assert stored_files == [], f"Expected no files in storage, found: {stored_files}"


# ---------------------------------------------------------------------------
# GET /api/v1/soundtracks
# ---------------------------------------------------------------------------


async def test_list_soundtracks(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /soundtracks lists uploaded soundtracks."""
    monkeypatch.setattr(
        soundtracks_service_module, "probe_audio", _stub_probe_audio(_GOOD_PROBE)
    )

    r1 = await client.post(
        "/api/v1/soundtracks",
        files={"file": ("track1.mp3", _FAKE_MP3, "audio/mpeg")},
    )
    assert r1.status_code == 201

    r2 = await client.post(
        "/api/v1/soundtracks",
        files={"file": ("track2.mp3", _FAKE_MP3, "audio/mpeg")},
    )
    assert r2.status_code == 201

    list_response = await client.get("/api/v1/soundtracks")
    assert list_response.status_code == 200
    soundtracks = list_response.json()
    assert len(soundtracks) == 2


async def test_list_soundtracks_limit_cap(
    client: AsyncClient,
) -> None:
    """limit > 200 is rejected with 422."""
    response = await client.get("/api/v1/soundtracks?limit=201")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/soundtracks/{id}
# ---------------------------------------------------------------------------


async def test_get_soundtrack_returns_correct_soundtrack(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /soundtracks/{id} returns the correct soundtrack."""
    monkeypatch.setattr(
        soundtracks_service_module, "probe_audio", _stub_probe_audio(_GOOD_PROBE)
    )

    created = await client.post(
        "/api/v1/soundtracks",
        files={"file": ("track.mp3", _FAKE_MP3, "audio/mpeg")},
    )
    soundtrack_id = created.json()["id"]

    response = await client.get(f"/api/v1/soundtracks/{soundtrack_id}")
    assert response.status_code == 200
    assert response.json()["id"] == soundtrack_id


async def test_get_unknown_soundtrack_returns_404(client: AsyncClient) -> None:
    """GET /soundtracks/{unknown_id} → 404."""
    response = await client.get(
        "/api/v1/soundtracks/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/soundtracks/{id}
# ---------------------------------------------------------------------------


async def test_delete_soundtrack_returns_204_then_404(
    client: AsyncClient,
    storage: LocalStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DELETE /soundtracks/{id} → 204; subsequent GET → 404; file gone from storage."""
    monkeypatch.setattr(
        soundtracks_service_module, "probe_audio", _stub_probe_audio(_GOOD_PROBE)
    )

    created = await client.post(
        "/api/v1/soundtracks",
        files={"file": ("track.mp3", _FAKE_MP3, "audio/mpeg")},
    )
    soundtrack_id = created.json()["id"]
    soundtrack_key = created.json()["key"]

    delete_response = await client.delete(f"/api/v1/soundtracks/{soundtrack_id}")
    assert delete_response.status_code == 204

    get_response = await client.get(f"/api/v1/soundtracks/{soundtrack_id}")
    assert get_response.status_code == 404

    # Verify file was deleted from storage.
    file_path = Path(storage.path_or_url(soundtrack_key))
    file_exists = await anyio.to_thread.run_sync(file_path.exists)
    assert not file_exists, f"Expected file to be deleted: {file_path}"


# ---------------------------------------------------------------------------
# GET /api/v1/soundtracks/{id}/audio
# ---------------------------------------------------------------------------


async def test_stream_audio_no_range_returns_200(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /soundtracks/{id}/audio with no Range → 200, Accept-Ranges, correct Content-Type, body matches."""
    monkeypatch.setattr(
        soundtracks_service_module, "probe_audio", _stub_probe_audio(_GOOD_PROBE)
    )

    created = await client.post(
        "/api/v1/soundtracks",
        files={"file": ("track.mp3", _FAKE_MP3, "audio/mpeg")},
    )
    assert created.status_code == 201
    soundtrack_id = created.json()["id"]

    response = await client.get(f"/api/v1/soundtracks/{soundtrack_id}/audio")
    assert response.status_code == 200
    assert response.headers.get("accept-ranges") == "bytes"
    assert "audio/mpeg" in response.headers.get("content-type", "")
    assert response.content == _FAKE_MP3


async def test_stream_audio_with_range_returns_206(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /soundtracks/{id}/audio with Range: bytes=0-3 → 206, correct Content-Range, first 4 bytes."""
    monkeypatch.setattr(
        soundtracks_service_module, "probe_audio", _stub_probe_audio(_GOOD_PROBE)
    )

    created = await client.post(
        "/api/v1/soundtracks",
        files={"file": ("track.mp3", _FAKE_MP3, "audio/mpeg")},
    )
    assert created.status_code == 201
    soundtrack_id = created.json()["id"]
    file_size = len(_FAKE_MP3)

    response = await client.get(
        f"/api/v1/soundtracks/{soundtrack_id}/audio",
        headers={"Range": "bytes=0-3"},
    )
    assert response.status_code == 206
    assert response.headers.get("content-range") == f"bytes 0-3/{file_size}"
    assert response.content == _FAKE_MP3[:4]


async def test_stream_audio_unknown_id_returns_404(client: AsyncClient) -> None:
    """GET /soundtracks/{unknown}/audio → 404."""
    response = await client.get(
        "/api/v1/soundtracks/00000000-0000-0000-0000-000000000000/audio"
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Cleanup on DB failure
# ---------------------------------------------------------------------------


async def test_upload_db_failure_cleans_up_file(
    client: AsyncClient,
    storage: LocalStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the DB write fails after a successful upload+probe, no file is left in storage.

    A bare RuntimeError is not an AppError so it propagates through the ASGI transport
    as an unhandled exception; we catch it and verify the service still deleted the file.
    """
    monkeypatch.setattr(
        soundtracks_service_module, "probe_audio", _stub_probe_audio(_GOOD_PROBE)
    )

    from app.domains.soundtracks.repository import SoundtrackRepository

    async def bad_add(self: SoundtrackRepository, entity: Soundtrack) -> Soundtrack:
        raise RuntimeError("DB failure")

    monkeypatch.setattr(SoundtrackRepository, "add", bad_add)

    with pytest.raises(RuntimeError, match="DB failure"):
        await client.post(
            "/api/v1/soundtracks",
            files={"file": ("song.mp3", _FAKE_MP3, "audio/mpeg")},
        )

    # No file should remain in storage — service.create_from_upload deletes on failure.
    soundtrack_dir = storage._base_dir / "soundtracks"
    if soundtrack_dir.exists():
        files = list(soundtrack_dir.iterdir())
        assert files == [], f"Orphaned files found: {files}"
