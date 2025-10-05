"""Incident recovery command handlers."""

from __future__ import annotations

from typing import Dict

from ..services import get_recovery_toolkit
from ..utils import logbook


def recover_safe(args) -> Dict[str, object]:
    manager = get_recovery_toolkit()
    result = manager.start_safe_recovery(args.safe_address)
    record = {
        "action": "recover_safe",
        "safe": result["safe"],
        "steps": result["steps"],
        "status": result["status"],
    }
    logbook.info(record)
    print(f"[RECOVER] Recovery wizard started for {result['safe']}")
    for step in result["steps"]:
        print(f"  • {step}")
    return record


def rotate_all(args=None) -> Dict[str, object]:
    manager = get_recovery_toolkit()
    result = manager.rotate_all()
    record = {
        "action": "recover_rotate_all",
        "timestamp": result["timestamp"],
        "owners": result["owners"],
        "status": result["status"],
    }
    logbook.info(record)
    print("[RECOVER] Executor wallets rotated and Safe owners updated.")
    return record


def freeze(args) -> Dict[str, object]:
    manager = get_recovery_toolkit()
    result = manager.freeze(args.target_type, args.target_id, args.reason)
    record = {
        "action": "recover_freeze",
        "target_type": result["target_type"],
        "target_id": result["target_id"],
        "reason": result["reason"],
        "unfreeze_token": result["unfreeze_token"],
    }
    logbook.info(record)
    print(f"[RECOVER] {result['target_type']} {result['target_id']} frozen. Token={result['unfreeze_token']}")
    return record
