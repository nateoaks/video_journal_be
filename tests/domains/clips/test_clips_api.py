"""Integration tests for the clips API endpoints."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

import app.domains.clips.service as clips_service_module
from app.media.ffprobe import FfprobeError, ProbeResult
from app.storage.local import LocalStorage

# A minimal MP4-like payload — content doesn't matter; probe is stubbed.
_FAKE_MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isomiso2"

_GOOD_PROBE = ProbeResult(
    duration_s=15.0,
    width=1920,
    height=1080,
    codec_name="h264",
    recorded_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
)


def _stub_probe(result: ProbeResult | Exception) -> Any:
    """Return an async callable that returns result or raises it."""
    if isinstance(result, Exception):
        exc = result

        async def _raise(_path: str | Path) -> ProbeResult:
            raise exc

        return _raise
    else:
        probe_result = result

        async def _return(_path: str | Path) -> ProbeResult:
            return probe_result

        return _return


# ---------------------------------------------------------------------------
# POST /api/v1/clips
# ---------------------------------------------------------------------------


async def test_upload_valid_mp4_returns_201(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Valid .mp4 upload → 201, body contains expected fields."""
    monkeypatch.setattr(clips_service_module, "probe", _stub_probe(_GOOD_PROBE))

    response = await client.post(
        "/api/v1/clips",
        files={"file": ("test.mp4", _FAKE_MP4, "video/mp4")},
    )

    assert response.status_code == 201
    body = response.json()
    assert "id" in body
    assert body["status"] == "processing"
    assert body["duration_s"] == pytest.approx(15.0)
    assert body["width"] == 1920
    assert body["height"] == 1080
    assert body["codec_name"] == "h264"


async def test_upload_avi_extension_returns_415(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unsupported .avi extension → 415 before any DB row is created."""
    monkeypatch.setattr(clips_service_module, "probe", _stub_probe(_GOOD_PROBE))

    response = await client.post(
        "/api/v1/clips",
        files={"file": ("clip.avi", _FAKE_MP4, "video/avi")},
    )

    assert response.status_code == 415

    # Verify no clip was persisted.
    list_response = await client.get("/api/v1/clips")
    assert list_response.json() == []


async def test_upload_ffprobe_failure_returns_422_and_no_db_row(
    client: AsyncClient,
    storage: LocalStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ffprobe fails the file is cleaned up and 422 is returned."""
    monkeypatch.setattr(
        clips_service_module,
        "probe",
        _stub_probe(FfprobeError("bad video")),
    )

    response = await client.post(
        "/api/v1/clips",
        files={"file": ("broken.mp4", _FAKE_MP4, "video/mp4")},
    )

    assert response.status_code == 422

    list_response = await client.get("/api/v1/clips")
    assert list_response.json() == []

    # Verify the storage file was deleted (no orphaned file left behind).
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
    monkeypatch.setattr(clips_service_module, "probe", _stub_probe(_GOOD_PROBE))

    # Patch settings to use a very small limit so the fake payload triggers it.
    from app.core.config import Settings

    monkeypatch.setattr(
        clips_service_module,
        "get_settings",
        lambda: Settings(max_upload_bytes=10),
    )

    response = await client.post(
        "/api/v1/clips",
        files={"file": ("big.mp4", _FAKE_MP4, "video/mp4")},
    )

    assert response.status_code == 413

    list_response = await client.get("/api/v1/clips")
    assert list_response.json() == []

    # Verify the partial storage file was cleaned up.
    media_dir = storage._base_dir
    stored_files = (
        [p for p in media_dir.rglob("*") if p.is_file()] if media_dir.exists() else []
    )
    assert stored_files == [], f"Expected no files in storage, found: {stored_files}"


# ---------------------------------------------------------------------------
# GET /api/v1/clips
# ---------------------------------------------------------------------------


async def test_list_clips_returns_clips_ordered_by_sort_index(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /clips returns all clips ordered by sort_index ascending."""
    # Upload two clips with different recorded_at so they get different sort indexes.
    probe_early = ProbeResult(
        duration_s=5.0,
        width=1280,
        height=720,
        codec_name="h264",
        recorded_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
    )
    probe_late = ProbeResult(
        duration_s=5.0,
        width=1280,
        height=720,
        codec_name="h264",
        recorded_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
    )

    monkeypatch.setattr(clips_service_module, "probe", _stub_probe(probe_late))
    r1 = await client.post(
        "/api/v1/clips",
        files={"file": ("late.mp4", _FAKE_MP4, "video/mp4")},
    )
    assert r1.status_code == 201

    monkeypatch.setattr(clips_service_module, "probe", _stub_probe(probe_early))
    r2 = await client.post(
        "/api/v1/clips",
        files={"file": ("early.mp4", _FAKE_MP4, "video/mp4")},
    )
    assert r2.status_code == 201

    list_response = await client.get("/api/v1/clips")
    assert list_response.status_code == 200
    clips = list_response.json()
    assert len(clips) == 2
    assert clips[0]["sort_index"] <= clips[1]["sort_index"]


async def test_list_clips_limit_cap(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """limit > 200 is rejected with 422."""
    monkeypatch.setattr(clips_service_module, "probe", _stub_probe(_GOOD_PROBE))

    response = await client.get("/api/v1/clips?limit=201")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/clips/{id}
# ---------------------------------------------------------------------------


async def test_get_clip_returns_correct_clip(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /clips/{id} returns the correct clip."""
    monkeypatch.setattr(clips_service_module, "probe", _stub_probe(_GOOD_PROBE))

    created = await client.post(
        "/api/v1/clips",
        files={"file": ("video.mp4", _FAKE_MP4, "video/mp4")},
    )
    clip_id = created.json()["id"]

    response = await client.get(f"/api/v1/clips/{clip_id}")
    assert response.status_code == 200
    assert response.json()["id"] == clip_id


async def test_get_unknown_clip_returns_404(client: AsyncClient) -> None:
    """GET /clips/{unknown_id} → 404."""
    response = await client.get("/api/v1/clips/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/clips/{id}
# ---------------------------------------------------------------------------


async def test_patch_updates_trim_points(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PATCH /clips/{id} updates trim_in_s and trim_out_s."""
    monkeypatch.setattr(clips_service_module, "probe", _stub_probe(_GOOD_PROBE))

    created = await client.post(
        "/api/v1/clips",
        files={"file": ("video.mp4", _FAKE_MP4, "video/mp4")},
    )
    clip_id = created.json()["id"]

    response = await client.patch(
        f"/api/v1/clips/{clip_id}",
        json={"trim_in_s": 2.0, "trim_out_s": 10.0},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["trim_in_s"] == pytest.approx(2.0)
    assert body["trim_out_s"] == pytest.approx(10.0)


async def test_patch_invalid_trim_returns_422(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PATCH with trim_in_s >= trim_out_s → 422."""
    monkeypatch.setattr(clips_service_module, "probe", _stub_probe(_GOOD_PROBE))

    created = await client.post(
        "/api/v1/clips",
        files={"file": ("video.mp4", _FAKE_MP4, "video/mp4")},
    )
    clip_id = created.json()["id"]

    response = await client.patch(
        f"/api/v1/clips/{clip_id}",
        json={"trim_in_s": 8.0, "trim_out_s": 5.0},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/v1/clips/{id}
# ---------------------------------------------------------------------------


async def test_delete_clip_returns_204_then_404(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DELETE /clips/{id} → 204; subsequent GET → 404."""
    monkeypatch.setattr(clips_service_module, "probe", _stub_probe(_GOOD_PROBE))

    created = await client.post(
        "/api/v1/clips",
        files={"file": ("video.mp4", _FAKE_MP4, "video/mp4")},
    )
    clip_id = created.json()["id"]

    delete_response = await client.delete(f"/api/v1/clips/{clip_id}")
    assert delete_response.status_code == 204

    get_response = await client.get(f"/api/v1/clips/{clip_id}")
    assert get_response.status_code == 404
