"""Command handlers for the wallet subsystem."""

from __future__ import annotations

import os
from dataclasses import asdict
from typing import Dict, List, Optional

from ..utils import logbook
from ..wallet import (
    DerivationResolver,
    WalletManager,
    WalletManagerError,
    WalletSeedError,
    WalletSeedManager,
)

_MANAGER: Optional[WalletManager] = None


def _service_name() -> str:
    return os.getenv("GNOMAN_KEYRING_SERVICE", "gnoman")


def _manager() -> WalletManager:
    global _MANAGER
    if _MANAGER is None:
        try:
            seed_manager = WalletSeedManager(service_name=_service_name())
        except WalletSeedError as exc:
            raise SystemExit(str(exc)) from exc
        resolver = DerivationResolver()
        _MANAGER = WalletManager(seed_manager=seed_manager, resolver=resolver)
    return _MANAGER


def new(args) -> Dict[str, object]:
    manager = _manager()
    try:
        record = manager.create_account(args.label, path=args.path)
    except WalletManagerError as exc:
        raise SystemExit(str(exc)) from exc
    payload = asdict(record)
    logbook.info({"action": "wallet_new", "label": record.label, "address": record.address, "path": record.derivation_path})
    print(f"[WALLET] {record.label} -> {record.address} ({record.derivation_path})")
    return payload


def list_accounts(args) -> Dict[str, List[Dict[str, object]]]:
    manager = _manager()
    records = [asdict(record) for record in manager.list_accounts()]
    logbook.info({"action": "wallet_list", "count": len(records)})
    for rec in records:
        print(f"[WALLET] {rec['label']} -> {rec['address']} ({rec['derivation_path']})")
    return {"accounts": records}


def vanity(args) -> Dict[str, object]:
    manager = _manager()
    try:
        record = manager.find_vanity(
            prefix=args.prefix,
            suffix=args.suffix,
            regex=args.regex,
            path=args.path,
            max_attempts=args.max_attempts,
            log_every=args.log_every,
        )
    except WalletManagerError as exc:
        raise SystemExit(str(exc)) from exc
    payload = asdict(record)
    logbook.info(
        {
            "action": "wallet_vanity",
            "address": record.address,
            "path": record.derivation_path,
            "index": record.index,
            "prefix": args.prefix,
            "suffix": args.suffix,
            "regex": args.regex,
        }
    )
    print(
        f"[WALLET] Vanity match {record.address} ({record.derivation_path}, index={record.index})"
    )
    return payload
