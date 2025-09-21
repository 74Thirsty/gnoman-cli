"""Synchronise GNOMAN secrets across environments."""

from __future__ import annotations

from typing import Dict, List, Tuple

from ..utils import aes, logbook


def run(args) -> Dict[str, object]:
    coordinator = aes.get_secrets_coordinator()
    snapshot = coordinator.snapshot()
    drift = coordinator.detect_drift(snapshot)

    if not drift:
        record = {
            "action": "sync",
            "status": "in-sync",
            "drift": {},
        }
        logbook.info(record)
        print("[SYNC] All stores already aligned.")
        return record

    mode = "inspect"
    operations: List[Dict[str, object]] = []

    if args.force:
        operations = coordinator.force_sync()
        mode = "force"
        print("[SYNC] Forced priority sync applied.")
    elif args.reconcile:
        operations = coordinator.reconcile_priority()
        mode = "priority"
        print("[SYNC] Drift reconciled using AES priority order.")
    else:
        print("[SYNC] Drift detected. Enter store to reconcile each key (leave blank for priority store).")
        decisions: Dict[str, Tuple[str, str]] = {}
        for key, stores in drift.items():
            priority_store, priority_value = coordinator.authoritative_value(key)
            options = ", ".join(f"{name}={value}" for name, value in stores.items())
            prompt = f"  - {key} ({options}) [{priority_store}]: "
            chosen_store = input(prompt).strip()  # noqa: PLW1508 - interactive prompt intentional
            if chosen_store not in stores:
                chosen_store = priority_store or next(iter(stores.keys()))
            chosen_value = stores.get(chosen_store, priority_value or "")
            decisions[key] = (chosen_store or "unknown", chosen_value)
        operations = coordinator.apply_decisions(decisions)
        mode = "interactive"
        print("[SYNC] Manual reconciliation complete.")

    reconciled = coordinator.snapshot()
    record = {
        "action": "sync",
        "status": "reconciled",
        "mode": mode,
        "drift": drift,
        "operations": operations,
        "result": reconciled,
    }
    logbook.info(record)
    print(f"[SYNC] Keys harmonised across {len(reconciled)} stores.")
    return record
