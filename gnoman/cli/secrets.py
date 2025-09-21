"""Keyring and environment management stubs."""

from __future__ import annotations

from typing import Dict, List

from ..utils import logbook


MASK = "***"


def list_secrets(args) -> Dict[str, List[Dict[str, str]]]:
    secrets = [
        {"key": "RPC_URL", "status": "active"},
        {"key": "SAFE_OWNER", "status": "stale"},
        {"key": "DISCORD_WEBHOOK", "status": "active"},
    ]
    record = {
        "action": "secrets_list",
        "entries": secrets,
        "status": "stub",
    }
    logbook.info(record)
    print(f"[SECRETS] Stored keys: {[entry['key'] for entry in secrets]}")
    return record


def add_secret(args) -> Dict[str, str]:
    record = {
        "action": "secrets_add",
        "key": args.key,
        "value": MASK,
        "status": "stub",
    }
    logbook.info(record)
    print(f"[SECRETS] Added key {args.key}")
    return record


def rotate_secret(args) -> Dict[str, str]:
    record = {
        "action": "secrets_rotate",
        "key": args.key,
        "status": "stub",
    }
    logbook.info(record)
    print(f"[SECRETS] Rotated key {args.key}")
    return record


def remove_secret(args) -> Dict[str, str]:
    record = {
        "action": "secrets_remove",
        "key": args.key,
        "status": "stub",
    }
    logbook.info(record)
    print(f"[SECRETS] Removed key {args.key}")
    return record
