"""Environment file discovery helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict


def get_gnoman_home() -> Path:
    """Return the GNOMAN workspace directory respecting :env:`GNOMAN_HOME`."""

    override = os.environ.get("GNOMAN_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".gnoman"


def env_file_paths(root: Path | None = None) -> Dict[str, Path]:
    """Return canonical paths to managed environment files."""

    base = root or Path.cwd()
    return {
        "env": base / ".env",
        "env_secure": base / ".env.secure",
    }


__all__ = ["env_file_paths", "get_gnoman_home"]
