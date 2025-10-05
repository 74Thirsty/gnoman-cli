"""Compatibility layer for legacy ABI helpers.

This module used to live under :mod:`gnoman.utils.abi`.  Recent refactors
moved the implementation into :mod:`gnoman.core.abi_manager`, but the legacy
CLI (``gnoman legacy``) still imports :func:`load_safe_abi` from the old
location.  Importing from here keeps the legacy interface stable while the
new Textual dashboard uses the richer ABI manager APIs.
"""

from __future__ import annotations

from typing import List, Dict, Any, Tuple
from pathlib import Path

from ..core import abi_manager

# Path to store the last used ABI selections.  The legacy CLI expects the
# helper to return both the ABI entries and the source path, so we keep that
# behaviour intact while delegating the heavy lifting to :mod:`abi_manager`.
ABI_STORE = Path.home() / ".gnoman" / "abi_store.json"


def load_safe_abi(path: str | None = None) -> Tuple[List[Dict[str, Any]], str]:
    """Load a Safe-compatible ABI definition.

    Parameters
    ----------
    path:
        Optional path to an ABI JSON file.  If omitted the helper will attempt
        to load the most recently used ABI path from ``ABI_STORE``.

    Returns
    -------
    tuple
        A pair consisting of the ABI entries and the file path that supplied
        them.  This mirrors the legacy helper API used by ``legacy.py``.
    """

    abi_path = _resolve_path(path)
    abi_entries = abi_manager.load_abi_from_file(abi_path)
    _remember_last_path(abi_path)
    return abi_entries, abi_path


def _resolve_path(path: str | None) -> str:
    if path:
        candidate = Path(path).expanduser()
        if not candidate.exists():
            raise FileNotFoundError(f"ABI file not found: {candidate}")
        return str(candidate)

    if ABI_STORE.exists():
        try:
            payload = abi_manager.load_store(ABI_STORE)
            stored = payload.get("last_path")
            if stored:
                stored_path = Path(stored).expanduser()
                if stored_path.exists():
                    return str(stored_path)
        except Exception:
            # Ignore corrupt store files – callers will be prompted for a path
            pass

    raise FileNotFoundError("No ABI path provided and no stored ABI available")


def _remember_last_path(path: str) -> None:
    try:
        abi_manager.update_store(ABI_STORE, path)
    except Exception:
        # Persisting the last used path is a best effort feature; legacy flows
        # should continue even if writing fails (e.g. read-only FS).
        pass


__all__ = ["load_safe_abi"]
