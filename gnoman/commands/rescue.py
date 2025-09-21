"""Incident recovery command handlers."""

from __future__ import annotations

from typing import Dict

from ..utils import aes, logbook


def rescue_safe(args) -> Dict[str, object]:
    manager = aes.get_recovery_manager()
    result = manager.start_safe_recovery(args.safe_address)
    record = {
        "action": "rescue_safe",
        "safe": result["safe"],
        "steps": result["steps"],
        "status": result["status"],
    }
    logbook.info(record)
    print(f"[RESCUE] Recovery wizard started for {result['safe']}")
    for step in result["steps"]:
        print(f"  • {step}")
    return record


def rotate_all(args=None) -> Dict[str, object]:
    manager = aes.get_recovery_manager()
    result = manager.rotate_all()
    record = {
        "action": "rotate_all",
        "timestamp": result["timestamp"],
        "owners": result["owners"],
        "status": result["status"],
    }
    logbook.info(record)
    print("[ROTATE] Executor wallets rotated and Safe owners updated.")
    return record


def freeze(args) -> Dict[str, object]:
    manager = aes.get_recovery_manager()
    result = manager.freeze(args.target_type, args.target_id, args.reason)
    record = {
        "action": "freeze",
        "target_type": result["target_type"],
        "target_id": result["target_id"],
        "reason": result["reason"],
        "unfreeze_token": result["unfreeze_token"],
    }
    logbook.info(record)
    print(f"[FREEZE] {result['target_type']} {result['target_id']} frozen. Token={result['unfreeze_token']}")
    return record
