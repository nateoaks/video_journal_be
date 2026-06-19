"""In-memory progress registry for active compilation renders.

One asyncio.Queue is held per running compilation.  The FFmpeg thread pushes
updates via loop.call_soon_threadsafe so the queue is always mutated from the
event-loop thread.  The SSE endpoint drains the queue until the terminal event
arrives, then exits.
"""

import asyncio
from dataclasses import dataclass, field
from uuid import UUID


@dataclass
class ProgressUpdate:
    """A single progress snapshot pushed from the FFmpeg thread."""

    progress: int
    status: str
    video_url: str | None = field(default=None)
    error: str | None = field(default=None)


# Active compilations: id → (loop, queue).  Removed when finalized.
_channels: dict[
    UUID, tuple[asyncio.AbstractEventLoop, asyncio.Queue[ProgressUpdate]]
] = {}

# Terminal state persisted after finalization so late-connecting clients get
# the final status immediately instead of hanging.
# Grows without bound — acceptable for single-process, single-user deployment.
_terminal: dict[UUID, ProgressUpdate] = {}


def register(compilation_id: UUID) -> asyncio.Queue[ProgressUpdate]:
    """Register a new compilation and return its progress queue.

    Must be called from the event-loop thread (i.e. inside an async context).
    Captures the running loop so that push_from_thread can schedule puts safely.
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[ProgressUpdate] = asyncio.Queue()
    _channels[compilation_id] = (loop, queue)
    return queue


def subscribe(compilation_id: UUID) -> asyncio.Queue[ProgressUpdate] | None:
    """Return the live queue for compilation_id, or None if not registered."""
    entry = _channels.get(compilation_id)
    return entry[1] if entry is not None else None


def get_terminal(compilation_id: UUID) -> ProgressUpdate | None:
    """Return the stored terminal update for compilation_id, or None."""
    return _terminal.get(compilation_id)


def push_from_thread(compilation_id: UUID, update: ProgressUpdate) -> None:
    """Push a progress update from a non-async thread.

    Uses loop.call_soon_threadsafe so the put is scheduled on the correct
    event-loop thread rather than called directly from the worker thread.
    """
    entry = _channels.get(compilation_id)
    if entry is None:
        return
    loop, queue = entry
    loop.call_soon_threadsafe(queue.put_nowait, update)


def unsubscribe(compilation_id: UUID) -> None:
    """Remove the channel for compilation_id without storing a terminal state.

    Called when the SSE client disconnects before the render finishes.  Guards
    against a concurrent finalize by only removing the entry if it still exists
    (finalize uses dict.pop which is also atomic under the GIL).
    """
    _channels.pop(compilation_id, None)


def finalize(compilation_id: UUID, update: ProgressUpdate) -> None:
    """Store the terminal state, remove the channel, and push the final event.

    After this call the queue receives exactly one more item (the terminal
    update) so the SSE generator can exit its drain loop cleanly.
    """
    _terminal[compilation_id] = update
    entry = _channels.pop(compilation_id, None)
    if entry is not None:
        loop, queue = entry
        loop.call_soon_threadsafe(queue.put_nowait, update)
