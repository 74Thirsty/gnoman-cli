"""Monitoring daemon for Safe configuration drift."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .core import AppContext, get_context
from .safe import SafeManager
from .sync import SecretSyncer


class GuardMonitor:
    """Poll Safe state and secret drift, emitting forensic records."""

    def __init__(self, context: Optional[AppContext] = None) -> None:
        self.context = context or get_context()
        self.safe = SafeManager(self.context)
        self.syncer = SecretSyncer(self.context)

    def run(self, *, cycles: int = 1, delay: float = 0.5) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        for cycle in range(1, cycles + 1):
            info = self.safe.info()
            drift = self.syncer.detect_drift()
            holds = self.safe.hold_entries()
            guard_address = info.get("guard")
            status = "ok"
            if drift:
                status = "drift"
            elif holds:
                status = "hold"
            elif not guard_address:
                status = "unguarded"
            record = {
                "cycle": cycle,
                "guard": guard_address,
                "holds": len(holds),
                "drift_keys": list(drift.keys()),
                "status": status,
            }
            records.append(record)
            self.context.ledger.log("guard_cycle", params={"cycle": cycle}, result=record)
            if delay > 0 and cycle < cycles:
                time.sleep(min(delay, 1.0))
        return records


def load_monitor(context: Optional[AppContext] = None) -> GuardMonitor:
    return GuardMonitor(context=context)
