"""Filesystem path helpers for GNOMAN state."""

from __future__ import annotations

import os
from pathlib import Path


def state_dir() -> Path:
    """Return the directory used for persistent GNOMAN state.

    The location defaults to ``~/.gnoman`` but can be overridden via the
    ``GNOMAN_STATE_DIR`` environment variable. The path is expanded and
    resolved so callers always receive an absolute location.
    """

    override = os.environ.get("GNOMAN_STATE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".gnoman"
