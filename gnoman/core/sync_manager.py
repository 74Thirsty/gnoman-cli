"""Secret synchronisation stubs."""

from __future__ import annotations

from .log_manager import log_event


class SyncManager:
    """Placeholder synchronisation engine."""

    def sync(self) -> None:
        log_event("sync", status="pending")
        raise NotImplementedError("Secret synchronisation is not yet implemented")


__all__ = ["SyncManager"]
