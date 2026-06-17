from collections.abc import AsyncIterator
from pathlib import Path

import anyio
import pytest

from app.core.config import get_settings
from app.storage import get_storage
from app.storage.local import LocalStorage


async def _stream(*chunks: bytes) -> AsyncIterator[bytes]:
    for chunk in chunks:
        yield chunk


@pytest.fixture
def storage(tmp_path: Path) -> LocalStorage:
    return LocalStorage(tmp_path)


async def test_save_and_open_round_trip(storage: LocalStorage) -> None:
    content = b"hello storage world"
    await storage.save(_stream(content), "test/file.bin")
    f = await storage.open("test/file.bin")
    try:
        assert f.read() == content
    finally:
        f.close()


async def test_path_or_url_exists_after_save(storage: LocalStorage) -> None:
    await storage.save(_stream(b"data"), "media/clip.mp4")
    path = storage.path_or_url("media/clip.mp4")
    assert await anyio.Path(path).exists()


async def test_delete_removes_file(storage: LocalStorage) -> None:
    await storage.save(_stream(b"x"), "to_delete.bin")
    assert await storage.exists("to_delete.bin")
    await storage.delete("to_delete.bin")
    assert not await storage.exists("to_delete.bin")


async def test_delete_is_idempotent(storage: LocalStorage) -> None:
    await storage.save(_stream(b"x"), "to_delete.bin")
    await storage.delete("to_delete.bin")
    await storage.delete("to_delete.bin")  # must not raise


async def test_exists_lifecycle(storage: LocalStorage) -> None:
    assert not await storage.exists("lifecycle.bin")
    await storage.save(_stream(b"y"), "lifecycle.bin")
    assert await storage.exists("lifecycle.bin")
    await storage.delete("lifecycle.bin")
    assert not await storage.exists("lifecycle.bin")


async def test_chunked_streaming_write(storage: LocalStorage) -> None:
    chunks = [b"chunk1-", b"chunk2-", b"chunk3"]
    await storage.save(_stream(*chunks), "chunked.bin")
    f = await storage.open("chunked.bin")
    try:
        assert f.read() == b"chunk1-chunk2-chunk3"
    finally:
        f.close()


async def test_save_creates_intermediate_directories(storage: LocalStorage) -> None:
    key = "clips/2024/abc123/original.mp4"
    await storage.save(_stream(b"video"), key)
    assert await anyio.Path(storage.path_or_url(key)).exists()


async def test_absolute_key_rejected(storage: LocalStorage) -> None:
    with pytest.raises(ValueError, match="relative"):
        await storage.save(_stream(b"x"), "/absolute/key.bin")


async def test_path_traversal_rejected(storage: LocalStorage) -> None:
    with pytest.raises(ValueError):
        await storage.save(_stream(b"x"), "../../escape.bin")


async def test_path_traversal_rejected_in_path_or_url(storage: LocalStorage) -> None:
    with pytest.raises(ValueError):
        storage.path_or_url("../outside.bin")


def test_get_storage_returns_local_storage_for_local_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    get_storage.cache_clear()
    get_settings.cache_clear()
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
    try:
        backend = get_storage()
        assert isinstance(backend, LocalStorage)
    finally:
        get_storage.cache_clear()
        get_settings.cache_clear()


def test_get_storage_raises_for_unknown_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_storage.cache_clear()
    get_settings.cache_clear()
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    try:
        with pytest.raises(ValueError, match="Unknown storage backend"):
            get_storage()
    finally:
        get_storage.cache_clear()
        get_settings.cache_clear()
