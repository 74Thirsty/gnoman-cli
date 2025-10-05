"""Command handlers for the wallet subsystem."""

from __future__ import annotations

import os
import getpass
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


def _seed_manager() -> WalletSeedManager:
    try:
        return WalletSeedManager(service_name=_service_name())
    except WalletSeedError as exc:
        raise SystemExit(str(exc)) from exc


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


def set_passphrase(args) -> Dict[str, object]:
    manager_cache_was_initialised = _MANAGER is not None
    seed_manager = _seed_manager()
    if args.clear:
        try:
            seed_manager.clear_passphrase()
        except WalletSeedError as exc:
            raise SystemExit(str(exc)) from exc
        logbook.info({"action": "wallet_passphrase", "mode": "cleared"})
        print("[WALLET] Cleared wallet passphrase")
        _reset_manager_cache()
        return {"cleared": True}

    if args.passphrase is not None:
        passphrase = args.passphrase
    else:
        prompt = "Enter new wallet passphrase: "
        confirm_prompt = "Confirm new wallet passphrase: "
        first = getpass.getpass(prompt)
        second = getpass.getpass(confirm_prompt)
        if first != second:
            raise SystemExit("passphrase confirmation does not match")
        passphrase = first

    if not passphrase:
        raise SystemExit("passphrase must not be empty; use --clear to remove it")
    try:
        seed_manager.store_passphrase(passphrase)
    except WalletSeedError as exc:
        raise SystemExit(str(exc)) from exc
    logbook.info({"action": "wallet_passphrase", "mode": "set", "cached": manager_cache_was_initialised})
    print("[WALLET] Updated wallet passphrase")
    _reset_manager_cache()
    return {"cleared": False}


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


def _reset_manager_cache() -> None:
    global _MANAGER
    _MANAGER = None
