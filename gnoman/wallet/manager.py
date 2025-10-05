"""High level wallet manager orchestrating derivations and vanity search."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from eth_account.signers.local import LocalAccount

from ..security import EncryptedJSONStore, EncryptedStoreError
from ..utils.paths import state_dir
from .hd import HDWalletTree
from .resolver import DerivationResolver, DerivationError
from .seed import SeedNotFoundError, WalletSeedError, WalletSeedManager
from .vanity import VanityGenerator, VanitySearchError

logger = logging.getLogger("gnoman.wallet")


class WalletManagerError(RuntimeError):
    """Raised for wallet management failures."""


@dataclass
class WalletRecord:
    label: str
    address: str
    derivation_path: str
    path_identifier: str
    index: int


@dataclass
class WalletManager:
    seed_manager: WalletSeedManager
    resolver: DerivationResolver
    state_path: Path = field(
        default_factory=lambda: state_dir() / "secrets" / "wallet_accounts.enc"
    )
    store: Optional[EncryptedJSONStore] = None

    def __post_init__(self) -> None:
        self._tree = HDWalletTree(self.seed_manager, self.resolver)
        self._store = self.store or EncryptedJSONStore(
            path=self.state_path,
            passphrase_resolver=self._resolve_passphrase,
        )
        self._accounts = self._load_state()

    # -- persistence -------------------------------------------------------
    def _load_state(self) -> Dict[str, WalletRecord]:
        try:
            payload = self._store.load({})
        except EncryptedStoreError as exc:
            raise WalletManagerError("failed to decrypt wallet inventory") from exc
        records: Dict[str, WalletRecord] = {}
        for label, data in payload.items():
            try:
                records[label] = WalletRecord(**data)
            except TypeError:
                continue
        return records

    def _save_state(self) -> None:
        serialisable = {label: record.__dict__ for label, record in self._accounts.items()}
        try:
            self._store.save(serialisable)
        except EncryptedStoreError as exc:
            raise WalletManagerError("failed to persist wallet inventory") from exc

    # -- helpers -----------------------------------------------------------
    def _next_index(self, path_identifier: str) -> int:
        indices = [r.index for r in self._accounts.values() if r.path_identifier == path_identifier]
        return max(indices, default=-1) + 1

    def _record(self, label: str) -> WalletRecord:
        if label not in self._accounts:
            raise WalletManagerError(f"unknown wallet label: {label}")
        return self._accounts[label]

    def _resolve_passphrase(self) -> str:
        try:
            passphrase = self.seed_manager.get_passphrase()
        except WalletSeedError as exc:
            raise WalletManagerError("failed to access wallet passphrase") from exc
        if not passphrase:
            raise WalletManagerError(
                "wallet passphrase not configured; run `gnoman wallet passphrase`"
            )
        return passphrase

    # -- public API --------------------------------------------------------
    def create_account(self, label: str, path: str = "default") -> WalletRecord:
        if label in self._accounts:
            raise WalletManagerError(f"label {label!r} already exists")
        try:
            index = self._next_index(path)
            address, _, derivation_path = self._tree.get_address(index, path_override=path)
        except SeedNotFoundError as exc:
            raise WalletManagerError("wallet seed not initialised") from exc
        except DerivationError as exc:
            raise WalletManagerError(str(exc)) from exc
        record = WalletRecord(label=label, address=address, derivation_path=derivation_path, path_identifier=path, index=index)
        self._accounts[label] = record
        self._save_state()
        logger.info("[WalletManager] 🧬 Derived address %s at path %s", address, derivation_path)
        return record

    def get_account(self, label: str) -> WalletRecord:
        return self._record(label)

    def get_signer(self, label: str) -> LocalAccount:
        record = self._record(label)
        try:
            address, account, _ = self._tree.get_address(record.index, path_override=record.path_identifier)
        except SeedNotFoundError as exc:
            raise WalletManagerError("wallet seed not initialised") from exc
        if address != record.address:
            logger.warning(
                "[WalletManager] address drift detected for label %s (expected %s, resolved %s)",
                label,
                record.address,
                address,
            )
        return account

    def list_accounts(self) -> List[WalletRecord]:
        return sorted(self._accounts.values(), key=lambda r: r.label)

    def find_vanity(
        self,
        *,
        prefix: Optional[str] = None,
        suffix: Optional[str] = None,
        regex: Optional[str] = None,
        path: str = "vanity",
        max_attempts: int = 1_000_000,
        log_every: int = 5_000,
    ) -> WalletRecord:
        generator = VanityGenerator(self._tree, path, log_every)
        try:
            result = generator.find_match(prefix=prefix, suffix=suffix, regex=regex, max_attempts=max_attempts)
        except VanitySearchError as exc:
            raise WalletManagerError(str(exc)) from exc
        address = result["address"]
        derivation_path = result["derivation_path"]
        index = result["index"]
        metadata_key = f"WALLET_VANITY::{address}".lower()
        try:
            self.seed_manager.store_metadata(
                metadata_key,
                json.dumps({"path": derivation_path, "index": index}),
            )
        except WalletSeedError as exc:
            raise WalletManagerError("failed to persist vanity metadata to keyring") from exc
        logger.info(
            "[WalletManager] 🧬 Derived address %s at path %s", address, derivation_path
        )
        return WalletRecord(
            label=f"vanity:{address[:8]}",
            address=address,
            derivation_path=derivation_path,
            path_identifier=path,
            index=index,
        )
