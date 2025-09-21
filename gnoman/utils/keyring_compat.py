"""Helpers for dealing with keyring availability across platforms.

This module tries to provide a best-effort keyring backend so that GNOMAN
continues to function on environments where the ``keyring`` package either is
not available or ships without a functional backend (e.g. iOS builds of
CPython).  The real keyring backend is preferred when present, otherwise a
small JSON-file based implementation is used as a fallback.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Dict, Optional

from .keyring_index import KeyringLike

logger = logging.getLogger(__name__)


def _default_storage_path() -> Path:
    """Return the path used by :class:`FileKeyring` when none is provided."""

    override = os.getenv("GNOMAN_KEYRING_PATH")
    if override:
        try:
            return Path(override).expanduser()
        except Exception:  # pragma: no cover - extremely defensive
            logger.debug("Invalid GNOMAN_KEYRING_PATH=%s", override, exc_info=True)
    return Path.home() / ".gnoman" / "keyring.json"


class FileKeyring:
    """Very small JSON backed keyring implementation.

    The implementation is intentionally tiny – it only supports the subset of
    functionality that GNOMAN requires (``get_password``, ``set_password`` and
    ``delete_password``).  All entries are namespaced by service and persisted
    to a single JSON file.  Access is guarded by a process-level lock so that
    concurrent callers do not trample over the file.
    """

    def __init__(self, storage_path: Optional[Path | str] = None) -> None:
        if storage_path is None:
            storage = _default_storage_path()
        else:
            storage = Path(storage_path)
        self.storage_path = storage.expanduser()
        self._lock = threading.Lock()

    # -- internal utilities -------------------------------------------------
    def _read_all(self) -> Dict[str, Dict[str, str]]:
        if not self.storage_path.exists():
            return {}
        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except Exception:
            logger.debug("Failed to read keyring file; assuming empty", exc_info=True)
            return {}
        result: Dict[str, Dict[str, str]] = {}
        if not isinstance(payload, dict):
            return result
        for service, entries in payload.items():
            if not isinstance(service, str) or not isinstance(entries, dict):
                continue
            normalised: Dict[str, str] = {}
            for key, value in entries.items():
                if isinstance(key, str) and isinstance(value, str):
                    normalised[key] = value
            if normalised:
                result[service] = normalised
        return result

    def _write_all(self, data: Dict[str, Dict[str, str]]) -> None:
        if not data:
            try:
                self.storage_path.unlink()
            except FileNotFoundError:
                return
            except Exception:  # pragma: no cover - failure to clean up is fine
                logger.debug("Failed to remove empty keyring file", exc_info=True)
                return
            return

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.storage_path.with_suffix(self.storage_path.suffix + ".tmp")
        try:
            tmp_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp_path, self.storage_path)
        except Exception as exc:
            logger.error("Failed to persist fallback keyring", exc_info=True)
            raise RuntimeError("failed to persist keyring data") from exc
        finally:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:  # pragma: no cover - best effort cleanup
                logger.debug("Failed to clean up temporary keyring file", exc_info=True)

    # -- public API ---------------------------------------------------------
    def get_password(self, service: str, key: str) -> Optional[str]:
        if not service or not key:
            return None
        with self._lock:
            data = self._read_all()
            return data.get(service, {}).get(key)

    def set_password(self, service: str, key: str, value: str) -> None:
        if not service or not key:
            raise ValueError("service and key must be non-empty strings")
        value = str(value)
        with self._lock:
            data = self._read_all()
            bucket = data.setdefault(service, {})
            bucket[key] = value
            self._write_all(data)

    def delete_password(self, service: str, key: str) -> None:
        if not service or not key:
            return
        with self._lock:
            data = self._read_all()
            bucket = data.get(service)
            if bucket and key in bucket:
                bucket.pop(key, None)
                if bucket:
                    data[service] = bucket
                else:
                    data.pop(service, None)
                self._write_all(data)


def _try_native_keyring() -> Optional[KeyringLike]:
    """Return the real keyring backend when usable, otherwise ``None``."""

    try:  # pragma: no branch - import depends on environment
        import keyring as native_keyring  # type: ignore
    except Exception:
        return None

    backend = None
    try:
        backend = native_keyring.get_keyring()
    except Exception:
        return None

    module_name = backend.__class__.__module__
    if module_name.startswith("keyring.backends.fail"):
        return None

    priority = getattr(backend, "priority", None)
    if isinstance(priority, (int, float)) and priority <= 0:
        return None

    try:
        native_keyring.get_password("__gnoman_probe__", "__gnoman_probe__")
    except Exception:
        return None

    return native_keyring  # type: ignore[return-value]


def load_keyring_backend(storage_path: Optional[Path | str] = None) -> Optional[KeyringLike]:
    """Return a keyring backend, preferring the system one when available.

    When the native keyring is unavailable (which is the case on several iOS
    Python distributions) a :class:`FileKeyring` instance is returned instead.
    The caller receives ``None`` only if both mechanisms fail which mirrors the
    previous behaviour of the application.
    """

    backend = _try_native_keyring()
    if backend is not None:
        logger.debug("Using native keyring backend: %s", backend)
        return backend

    try:
        fallback = FileKeyring(storage_path=storage_path)
    except Exception:
        logger.error("Unable to initialise fallback keyring", exc_info=True)
        return None

    logger.info("Using file-based fallback keyring located at %s", fallback.storage_path)
    return fallback


__all__ = ["FileKeyring", "load_keyring_backend"]

