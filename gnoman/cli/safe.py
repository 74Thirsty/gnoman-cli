"""Stub handlers for Safe lifecycle commands."""

from __future__ import annotations

from typing import Dict

from ..utils import logbook


def propose(args) -> Dict[str, str]:
    """Record a new Safe proposal stub."""

    record = {
        "action": "safe_propose",
        "to": args.to,
        "value": args.value,
        "data": args.data or "0x",
        "status": "stub",
    }
    logbook.info(record)
    print(f"[SAFE] Proposed tx: {record}")
    return record


def sign(args) -> Dict[str, str]:
    """Record a Safe signature stub."""

    record = {
        "action": "safe_sign",
        "proposal_id": args.proposal_id,
        "status": "stub",
    }
    logbook.info(record)
    print(f"[SAFE] Signed proposal {args.proposal_id}")
    return record


def exec(args) -> Dict[str, str]:
    """Record a Safe execution stub."""

    record = {
        "action": "safe_exec",
        "proposal_id": args.proposal_id,
        "status": "stub",
    }
    logbook.info(record)
    print(f"[SAFE] Executed proposal {args.proposal_id}")
    return record


def status(args) -> Dict[str, object]:
    """Return placeholder Safe status information."""

    record = {
        "action": "safe_status",
        "safe_address": args.safe_address,
        "owners": ["0xOwnerA", "0xOwnerB", "0xOwnerC"],
        "threshold": 2,
        "queued": [
            {"id": "1", "to": "0xabc", "value": "1 ETH", "status": "pending"},
            {"id": "2", "to": "0xdef", "value": "0.5 ETH", "status": "signed"},
        ],
        "status": "stub",
    }
    logbook.info(record)
    print(f"[SAFE] Status for {args.safe_address}: {record}")
    return record
