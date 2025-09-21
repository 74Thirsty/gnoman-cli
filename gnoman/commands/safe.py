"""Handlers for Safe lifecycle commands."""

from __future__ import annotations

from typing import Dict

from ..utils import aes, logbook


_DEF_SAFE = "0xSAFECORE"


def _registry() -> aes.SafeRegistry:
    return aes.get_safe_registry()


def propose(args) -> Dict[str, object]:
    proposal = _registry().propose(args.to, args.value, args.data or "0x")
    record = {
        "action": "safe_propose",
        "safe": _DEF_SAFE,
        "proposal": proposal,
    }
    logbook.info(record)
    print(f"[SAFE] Proposed tx #{proposal['id']} to {proposal['to']} value={proposal['value']}")
    return record


def sign(args) -> Dict[str, object]:
    proposal = _registry().sign(args.proposal_id)
    record = {
        "action": "safe_sign",
        "proposal": proposal,
    }
    logbook.info(record)
    print(f"[SAFE] Signed proposal {proposal['id']} status={proposal['status']}")
    return record


def exec(args) -> Dict[str, object]:
    proposal = _registry().execute(args.proposal_id)
    record = {
        "action": "safe_exec",
        "proposal": proposal,
    }
    logbook.info(record)
    print(f"[SAFE] Executed proposal {proposal['id']} status={proposal['status']}")
    return record


def status(args) -> Dict[str, object]:
    info = _registry().status(args.safe_address)
    record = {
        "action": "safe_status",
        "safe": info,
    }
    logbook.info(record)
    print(f"[SAFE] Status for {info['address']}: threshold={info.get('threshold')} owners={len(info.get('owners', []))}")
    return record
