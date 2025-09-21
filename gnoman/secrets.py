"""Direct secret store manipulation helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .core import AppContext, get_context
from .sync import SecretSyncer


class SecretManager:
    """Wrap :class:`SecretSyncer` for CLI parity with legacy commands."""

    def __init__(self, context: Optional[AppContext] = None) -> None:
        self.context = context or get_context()
        self.syncer = SecretSyncer(self.context)

    def list(self) -> List[Dict[str, Any]]:
        records = self.syncer.list_status()
        self.context.ledger.log("secrets_list", result={"count": len(records)})
        return records

    def add(self, key: str, value: str) -> Dict[str, Any]:
        self.syncer.set_secret(key, value)
        payload = {"stored": key}
        self.context.ledger.log("secrets_add", params={"key": key})
        return payload

    def rotate(self, key: str) -> Dict[str, Any]:
        value = self.syncer.rotate_secret(key)
        payload = {"key": key, "preview": value[:4] + "***"}
        self.context.ledger.log("secrets_rotate", params={"key": key})
        return payload

    def remove(self, key: str) -> Dict[str, Any]:
        self.syncer.remove_secret(key)
        payload = {"removed": key}
        self.context.ledger.log("secrets_remove", params={"key": key})
        return payload


def load_manager(context: Optional[AppContext] = None) -> SecretManager:
    return SecretManager(context=context)
