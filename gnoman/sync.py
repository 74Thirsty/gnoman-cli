"""Secrets synchronisation routines."""

from __future__ import annotations

import secrets
from typing import Dict, List, Optional

from .core import AppContext, get_context


class SecretSyncer:
    """Coordinate reconciliation between keyring and ``.env`` sources."""

    def __init__(self, context: Optional[AppContext] = None) -> None:
        self.context = context or get_context()

    # -- snapshot ---------------------------------------------------------
    def snapshot(self) -> Dict[str, Dict[str, Optional[str]]]:
        data = self.context.secrets.snapshot()
        self.context.ledger.log("sync_snapshot", result={"keys": len(data)})
        return data

    def detect_drift(self) -> Dict[str, Dict[str, Optional[str]]]:
        snapshot = self.snapshot()
        drift: Dict[str, Dict[str, Optional[str]]] = {}
        for key, sources in snapshot.items():
            values = [value for value in sources.values() if value is not None]
            if not values:
                continue
            if len(set(values)) > 1:
                drift[key] = sources
        self.context.ledger.log("sync_drift", result={"keys": list(drift.keys())})
        return drift

    # -- reconciliation ---------------------------------------------------
    def force_sync(self) -> List[Dict[str, str]]:
        actions: List[Dict[str, str]] = []
        snapshot = self.context.secrets.snapshot()
        for key, sources in snapshot.items():
            if "keyring" in sources and sources["keyring"] is not None:
                value = sources["keyring"]
                source = "keyring"
            elif "env" in sources and sources["env"] is not None:
                value = sources["env"]
                source = "env"
            else:
                continue
            self.context.secrets.set(key, value)
            actions.append({"key": key, "source": source})
        self.context.ledger.log("sync_force", result={"count": len(actions)})
        return actions

    def apply_decisions(self, decisions: Dict[str, str]) -> List[Dict[str, str]]:
        snapshot = self.context.secrets.snapshot()
        applied: List[Dict[str, str]] = []
        for key, source in decisions.items():
            sources = snapshot.get(key, {})
            value = sources.get(source)
            if value is None:
                continue
            self.context.secrets.set(key, value)
            applied.append({"key": key, "source": source})
        self.context.ledger.log("sync_apply", result={"count": len(applied)})
        return applied

    # -- management -------------------------------------------------------
    def list_status(self) -> List[Dict[str, object]]:
        snapshot = self.context.secrets.snapshot()
        records: List[Dict[str, object]] = []
        for key, sources in snapshot.items():
            values = {src: val for src, val in sources.items() if val is not None}
            status = "ok" if len(set(values.values())) <= 1 else "drift"
            meta = self.context.secrets.metadata(key)
            records.append({
                "key": key,
                "status": status,
                "sources": list(values.keys()),
                **{f"meta_{k}": v for k, v in meta.items()},
            })
        self.context.ledger.log("sync_list", result={"count": len(records)})
        return records

    def set_secret(self, key: str, value: str) -> None:
        self.context.secrets.set(key, value)

    def rotate_secret(self, key: str) -> str:
        new_value = secrets.token_hex(16)
        self.context.secrets.set(key, new_value)
        self.context.ledger.log("sync_rotate", params={"key": key})
        return new_value

    def remove_secret(self, key: str) -> None:
        self.context.secrets.delete(key)
        self.context.ledger.log("sync_remove", params={"key": key})


def load_syncer(context: Optional[AppContext] = None) -> SecretSyncer:
    return SecretSyncer(context=context)
