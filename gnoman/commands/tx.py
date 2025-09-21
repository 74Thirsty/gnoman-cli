"""Transaction simulation and execution handlers."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict

from ..utils import aes, logbook


def simulate(args) -> Dict[str, object]:
    engine = aes.get_simulation_engine()
    result = engine.simulate(
        proposal_id=getattr(args, "proposal_id", None),
        plan_path=getattr(args, "plan", None),
        trace=bool(getattr(args, "trace", False)),
        ml_enabled=not bool(getattr(args, "ml_off", False)),
    )
    record = {
        "action": "tx_simulate",
        "proposal_id": result["proposal_id"],
        "plan_digest": result["plan_digest"],
        "gas_used": result["gas_used"],
        "success": result["success"],
        "revert_reason": result["revert_reason"],
        "ml_score": result["ml_score"],
        "trace": result["trace"],
    }
    logbook.info(record)
    status = "ok" if result["success"] else f"reverted ({result['revert_reason']})"
    print(f"[TX] Simulation {result['plan_digest']} gas={result['gas_used']} status={status}")
    if result["trace"]:
        print("[TX] Trace:")
        for line in result["trace"]:
            print(f"    {line}")
    if result["ml_score"] is not None:
        print(f"[TX] ML score: {result['ml_score']}")
    return record


def exec(args) -> Dict[str, object]:
    payload_path = Path.home() / ".gnoman" / "queued" / f"{args.proposal_id}.json"
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "proposal_id": args.proposal_id,
        "broadcast_at": int(time.time()),
    }
    payload_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    record = {
        "action": "tx_exec",
        "proposal_id": args.proposal_id,
        "status": "queued",
        "payload_path": str(payload_path),
    }
    logbook.info(record)
    print(f"[TX] Execution payload queued at {payload_path}")
    return record
