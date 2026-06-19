"""Utility helpers for the compilations domain."""

import uuid


def build_output_key(compilation_id: uuid.UUID) -> str:
    """Return the storage key for a compilation's rendered MP4 output."""
    return f"outputs/{compilation_id}.mp4"
