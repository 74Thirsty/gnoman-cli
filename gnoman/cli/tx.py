"""Transaction simulation and execution stubs."""

from __future__ import annotations

from typing import Dict

from ..utils import logbook


def simulate(args) -> Dict[str, str]:
    record = {
        "action": "tx_simulate",
        "proposal_id": args.proposal_id,
        "status": "stub",
        "result": "success",
    }
    logbook.info(record)
    print(f"[TX] Simulated proposal {args.proposal_id}")
    return record


def exec(args) -> Dict[str, str]:
    record = {
        "action": "tx_exec",
        "proposal_id": args.proposal_id,
        "status": "stub",
    }
    logbook.info(record)
    print(f"[TX] Executed proposal {args.proposal_id}")
    return record
