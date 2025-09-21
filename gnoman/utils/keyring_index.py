"""Helpers for tracking key names stored in a keyring backend."""

from __future__ import annotations

import json
import logging
from typing import Iterable, List, Optional, Protocol, Sequence

logger = logging.getLogger(__name__)

INDEX_KEY = "__gnoman_key_index__"


class KeyringLike(Protocol):
    """Protocol describing the subset of keyring functionality we rely on."""

    def get_password(self, service: str, key: str) -> Optional[str]:
        ...

    def set_password(self, service: str, key: str, value: str) -> None:
        ...

    def delete_password(self, service: str, key: str) -> None:
        ...


def _normalise_keys(keys: Iterable[str]) -> List[str]:
    seen: dict[str, None] = {}
    for item in keys:
        if isinstance(item, str) and item:
            seen[item] = None
    return sorted(seen.keys())


def _load_index(backend: KeyringLike, service: str) -> List[str]:
    try:
        raw = backend.get_password(service, INDEX_KEY)
    except Exception:  # pragma: no cover - backend specific failure
        return []
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except Exception:
        return []
    if not isinstance(payload, Sequence):
        return []
    return _normalise_keys(str(item) for item in payload)


def _store_index(backend: KeyringLike, service: str, keys: Iterable[str]) -> None:
    payload = json.dumps(_normalise_keys(keys))
    try:
        backend.set_password(service, INDEX_KEY, payload)
    except Exception:  # pragma: no cover - backend specific failure
        logger.debug("Failed to persist keyring index", exc_info=True)


def register_key(backend: Optional[KeyringLike], service: str, key: str) -> None:
    """Record *key* in the index for *service* if possible."""

    if backend is None or not key or key == INDEX_KEY:
        return
    existing = _load_index(backend, service)
    if key in existing:
        return
    existing.append(key)
    _store_index(backend, service, existing)


def unregister_key(backend: Optional[KeyringLike], service: str, key: str) -> None:
    """Remove *key* from the index if it is present."""

    if backend is None or not key or key == INDEX_KEY:
        return
    existing = _load_index(backend, service)
    if key not in existing:
        return
    existing = [item for item in existing if item != key]
    if existing:
        _store_index(backend, service, existing)
    else:
        try:
            backend.delete_password(service, INDEX_KEY)
        except Exception:  # pragma: no cover - backend specific failure
            logger.debug("Failed to clear empty keyring index", exc_info=True)


def list_keys(backend: Optional[KeyringLike], service: str) -> List[str]:
    """Return the known keys for *service* tracked in the index."""

    if backend is None:
        return []
    return _load_index(backend, service)
