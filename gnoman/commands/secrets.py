"""Keyring and environment management commands."""

from __future__ import annotations

from typing import Dict, List

from ..utils import aes, logbook

MASK = "***"


def _coordinator() -> aes.SecretsSyncCoordinator:
    return aes.get_secrets_coordinator()


def list_secrets(args) -> Dict[str, List[Dict[str, object]]]:
    coordinator = _coordinator()
    snapshot = coordinator.snapshot()
    entries: List[Dict[str, object]] = []
    for key in coordinator.keys():
        values = {store: store_values.get(key) for store, store_values in snapshot.items() if key in store_values}
        status = "ok" if len(set(values.values())) == 1 else "drift"
        meta = coordinator.metadata(key)
        entries.append(
            {
                "key": key,
                "status": status,
                "sources": list(values.keys()),
                "expires_at": meta.get("expires_at"),
            }
        )
    record = {
        "action": "secrets_list",
        "entries": entries,
        "status": "ok",
    }
    logbook.info(record)
    print(f"[SECRETS] {len(entries)} secrets tracked. Drift keys: {[e['key'] for e in entries if e['status'] == 'drift']}")
    return record


def add_secret(args) -> Dict[str, object]:
    coordinator = _coordinator()
    coordinator.set_secret(args.key, args.value)
    record = {
        "action": "secrets_add",
        "key": args.key,
        "value": MASK,
        "status": "stored",
    }
    logbook.info(record)
    print(f"[SECRETS] Added key {args.key}")
    return record


def rotate_secret(args) -> Dict[str, object]:
    coordinator = _coordinator()
    new_value = coordinator.rotate_secret(args.key)
    record = {
        "action": "secrets_rotate",
        "key": args.key,
        "value": MASK,
        "status": "rotated",
        "preview": new_value[:4] + MASK,
    }
    logbook.info(record)
    print(f"[SECRETS] Rotated key {args.key}")
    return record


def remove_secret(args) -> Dict[str, object]:
    coordinator = _coordinator()
    coordinator.remove_secret(args.key)
    record = {
        "action": "secrets_remove",
        "key": args.key,
        "status": "removed",
    }
    logbook.info(record)
    print(f"[SECRETS] Removed key {args.key}")
    return record
