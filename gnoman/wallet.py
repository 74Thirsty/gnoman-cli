"""Wallet subsystem façade exposing CLI-friendly operations."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional

from eth_account.hdaccount import generate_mnemonic
from web3 import Web3

from .core import AppContext, get_context
from .wallet_core import (
    DerivationError,
    DerivationResolver,
    HDWalletTree,
    SeedNotFoundError,
    VanityGenerator,
    VanitySearchError,
    WalletManager,
    WalletManagerError,
    WalletSeedError,
    WalletSeedManager,
)
from .wallet_core.manager import WalletRecord

__all__ = [
    "DerivationError",
    "DerivationResolver",
    "HDWalletTree",
    "SeedNotFoundError",
    "VanityGenerator",
    "VanitySearchError",
    "WalletManager",
    "WalletManagerError",
    "WalletRecord",
    "WalletSeedError",
    "WalletSeedManager",
    "WalletService",
]


class WalletService:
    """High-level manager for mnemonic, derivation, and account workflows."""

    def __init__(self, context: Optional[AppContext] = None) -> None:
        self.context = context or get_context()
        self.seed_manager = WalletSeedManager(service_name=self.context.secrets.service_name)
        self.resolver = DerivationResolver()
        self.manager = WalletManager(seed_manager=self.seed_manager, resolver=self.resolver)
        self.tree = HDWalletTree(self.seed_manager, self.resolver)
        self.labels_path = Path.home() / ".gnoman" / "wallet_labels.json"
        self._labels = self._load_labels()
        self._discovered: List[Dict[str, str]] = []

    # -- label helpers ----------------------------------------------------
    def _load_labels(self) -> Dict[str, str]:
        if not self.labels_path.exists():
            return {}
        try:
            return json.loads(self.labels_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_labels(self) -> None:
        self.labels_path.parent.mkdir(parents=True, exist_ok=True)
        self.labels_path.write_text(json.dumps(self._labels, indent=2), encoding="utf-8")

    # -- mnemonic management ----------------------------------------------
    def generate_mnemonic(self) -> Dict[str, str]:
        phrase = generate_mnemonic()
        self.seed_manager.store_mnemonic(phrase)
        address, _, path = self.tree.get_address(0, path_override="default")
        self.context.ledger.log(
            "wallet_generate_mnemonic",
            result={"address": address, "path": path},
        )
        return {"mnemonic": phrase, "default_address": address, "path": path}

    def import_mnemonic(self, mnemonic: str) -> Dict[str, str]:
        self.seed_manager.store_mnemonic(mnemonic.strip())
        address, _, path = self.tree.get_address(0, path_override="default")
        self.context.ledger.log(
            "wallet_import_mnemonic",
            result={"address": address, "path": path},
        )
        return {"default_address": address, "path": path}

    def set_passphrase(self, passphrase: str) -> None:
        self.seed_manager.store_passphrase(passphrase)
        self.context.ledger.log("wallet_passphrase", params={"set": bool(passphrase)})

    def clear_passphrase(self) -> None:
        self.seed_manager.clear_passphrase()
        self.context.ledger.log("wallet_passphrase", params={"set": False})

    # -- derivations ------------------------------------------------------
    def derive(self, path: str) -> Dict[str, str]:
        address, _, derivation_path = self.tree.get_address(0, path_override=path)
        self.context.ledger.log("wallet_derive", params={"path": path}, result={"address": address})
        return {"address": address, "path": derivation_path}

    def scan(self, count: int, *, hidden: bool = False) -> List[Dict[str, str]]:
        base = "hidden" if hidden else "default"
        discovered: List[Dict[str, str]] = []
        for index in range(count):
            identifier = base
            try:
                address, _, path = self.tree.get_address(index, path_override=identifier)
            except SeedNotFoundError as exc:  # pragma: no cover - handled by CLI
                raise WalletManagerError(str(exc)) from exc
            discovered.append({"path": path, "address": address})
        self._discovered = discovered
        self.context.ledger.log(
            "wallet_scan",
            params={"count": count, "hidden": hidden},
            result={"addresses": [entry["address"] for entry in discovered]},
        )
        return discovered

    def discovered(self) -> List[Dict[str, str]]:
        return list(self._discovered)

    # -- account registry -------------------------------------------------
    def list_accounts(self) -> List[Dict[str, object]]:
        records = [asdict(record) for record in self.manager.list_accounts()]
        self.context.ledger.log("wallet_list_accounts", result={"count": len(records)})
        for record in records:
            record["label"] = record.get("label")
        return records

    def create_account(self, label: str, path: str = "default") -> Dict[str, object]:
        record = self.manager.create_account(label, path=path)
        payload = asdict(record)
        self.context.ledger.log(
            "wallet_create_account",
            params={"label": label, "path": path},
            result={"address": record.address},
        )
        return payload

    def find_vanity(
        self,
        *,
        prefix: Optional[str] = None,
        suffix: Optional[str] = None,
        regex: Optional[str] = None,
        path: str = "vanity",
        max_attempts: int = 1_000_000,
        log_every: int = 5_000,
    ) -> Dict[str, object]:
        record = self.manager.find_vanity(
            prefix=prefix,
            suffix=suffix,
            regex=regex,
            path=path,
            max_attempts=max_attempts,
            log_every=log_every,
        )
        payload = asdict(record)
        self.context.ledger.log(
            "wallet_vanity",
            params={"prefix": prefix, "suffix": suffix, "regex": regex},
            result={"address": record.address, "path": record.derivation_path},
        )
        return payload

    # -- metadata ---------------------------------------------------------
    def label_address(self, address: str, label: str) -> None:
        checksum = Web3.to_checksum_address(address)
        self._labels[checksum] = label
        self._write_labels()
        self.context.ledger.log("wallet_label", params={"address": checksum, "label": label})

    def export_discovered(self, path: Optional[Path] = None) -> Path:
        target = path or (Path.cwd() / "wallet_export.json")
        payload = {
            "discovered": self._discovered,
            "labels": self._labels,
        }
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.context.ledger.log("wallet_export", result={"path": str(target)})
        return target


def load_service(context: Optional[AppContext] = None) -> WalletService:
    return WalletService(context=context)
