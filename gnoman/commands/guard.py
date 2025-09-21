"""Guard monitoring command implementation."""

from __future__ import annotations

from typing import Dict

from ..utils import aes, logbook


def run(args) -> Dict[str, object]:
    guardian = aes.get_guardian()
    result = guardian.run(int(getattr(args, "cycles", 3)))
    record = {
        "action": "guard_start",
        "status": "completed",
        "cycles": result["cycles"],
        "alerts": result["alerts"],
        "channels": result["alert_channels"],
    }
    logbook.info(record)
    for cycle in result["cycles"]:
        print(
            "[GUARD] cycle="
            f"{cycle['timestamp']} secrets={'ok' if cycle['secrets_ok'] else 'drift'} "
            f"gas={cycle['gas_gwei']} gwei routes={len(cycle['profitable_routes'])}"
        )
    if result["alerts"]:
        print(f"[GUARD] Alerts dispatched via {', '.join(result['alert_channels'])}")
    else:
        print("[GUARD] No alerts raised.")
    return record
