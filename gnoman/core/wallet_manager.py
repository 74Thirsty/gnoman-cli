"""Hierarchical deterministic wallet management."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3
from web3.providers.eth_tester import EthereumTesterProvider

try:  # pragma: no cover - optional dependency
    from bip_utils import (
        Bip39MnemonicGenerator,
        Bip39SeedGenerator,
        Bip39WordsNum,
        Bip44,
        Bip44Coins,
    )
except Exception:  # pragma: no cover - dependency may be absent during tests
    Bip39MnemonicGenerator = None  # type: ignore[assignment]

from ..utils import keyring_backend
from ..utils.crypto_tools import decrypt_with_passphrase, encrypt_with_passphrase
from ..utils.env_tools import get_gnoman_home
from .log_manager import log_event


Account.enable_unaudited_hdwallet_features()


DEFAULT_DERIVATION_PATH = "m/44'/60'/0'/0/0"
KEYRING_SERVICE = "gnoman.wallet"


@dataclass
class WalletRecord:
    """Stored metadata for a managed wallet."""

    label: str
    address: str
    derivation_path: str
    created: datetime
    modified: datetime
    network: Optional[str] = None
    metadata: Dict[str, object] = field(default_factory=dict)


class WalletManager:
    """Manage HD wallets backed by the system keyring."""

    def __init__(self, *, base_path: Optional[Path] = None, rpc_url: Optional[str] = None) -> None:
        self._home = base_path or get_gnoman_home()
        self._store_path = self._home / "wallets.json"
        self._rpc_url = rpc_url or os.getenv("GNOMAN_ETH_RPC")
        self._web3: Optional[Web3] = None

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _load_store(self) -> Dict[str, Dict[str, object]]:
        if not self._store_path.exists():
            return {}
        try:
            payload = json.loads(self._store_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        if not isinstance(payload, list):
            return {}
        store: Dict[str, Dict[str, object]] = {}
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            label = str(entry.get("label", "")).strip()
            if not label:
                continue
            store[label] = dict(entry)
        return store

    def _save_store(self, store: Dict[str, Dict[str, object]]) -> None:
        payload = list(store.values())
        self._home.mkdir(parents=True, exist_ok=True)
        self._store_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # ------------------------------------------------------------------
    # HD wallet primitives
    # ------------------------------------------------------------------
    @staticmethod
    def _generate_mnemonic(words: int = 12) -> str:
        if Bip39MnemonicGenerator is not None:  # pragma: no cover - depends on optional dependency
            mapping = {
                12: Bip39WordsNum.WORDS_NUM_12,
                15: Bip39WordsNum.WORDS_NUM_15,
                18: Bip39WordsNum.WORDS_NUM_18,
                21: Bip39WordsNum.WORDS_NUM_21,
                24: Bip39WordsNum.WORDS_NUM_24,
            }
            mnemonic_obj = Bip39MnemonicGenerator().FromWordsNumber(mapping.get(words, Bip39WordsNum.WORDS_NUM_12))
            return str(mnemonic_obj)
        # Fallback to eth-account generator when bip_utils is unavailable
        from eth_account.hdaccount import generate_mnemonic

        return generate_mnemonic(num_words=words, lang="english")

    @staticmethod
    def _derive_account(mnemonic: str, *, derivation_path: str, passphrase: str) -> Account:
        if Bip39MnemonicGenerator is not None:  # pragma: no cover - depends on optional dependency
            seed_bytes = Bip39SeedGenerator(mnemonic).Generate(passphrase)
            bip_obj = Bip44.FromSeed(seed_bytes, Bip44Coins.ETHEREUM)
            node = bip_obj.DerivePath(derivation_path)
            private_key = node.PrivateKey().Raw().ToBytes()
            return Account.from_key(private_key)
        return Account.from_mnemonic(mnemonic, account_path=derivation_path, passphrase=passphrase)

    def _store_wallet(
        self,
        *,
        label: str,
        mnemonic: str,
        derivation_path: str,
        passphrase: str,
        network: Optional[str],
    ) -> WalletRecord:
        account = self._derive_account(mnemonic, derivation_path=derivation_path, passphrase=passphrase)
        keyring_backend.set_entry(KEYRING_SERVICE, label, mnemonic)
        now = datetime.now(timezone.utc)
        store = self._load_store()
        store[label] = {
            "label": label,
            "address": account.address,
            "derivation_path": derivation_path,
            "created": store.get(label, {}).get("created", now.isoformat()),
            "modified": now.isoformat(),
            "network": network,
            "mnemonic_passphrase": passphrase,
        }
        self._save_store(store)
        record = WalletRecord(
            label=label,
            address=account.address,
            derivation_path=derivation_path,
            created=datetime.fromisoformat(store[label]["created"]),
            modified=now,
            network=network,
        )
        log_event("wallet.create", label=label, address=account.address, network=network or "tester")
        return record

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def list_wallets(self) -> List[WalletRecord]:
        store = self._load_store()
        records: List[WalletRecord] = []
        for entry in store.values():
            try:
                created = datetime.fromisoformat(str(entry.get("created")))
            except Exception:
                created = datetime.now(timezone.utc)
            try:
                modified = datetime.fromisoformat(str(entry.get("modified")))
            except Exception:
                modified = created
            records.append(
                WalletRecord(
                    label=str(entry.get("label")),
                    address=str(entry.get("address")),
                    derivation_path=str(entry.get("derivation_path", DEFAULT_DERIVATION_PATH)),
                    created=created,
                    modified=modified,
                    network=entry.get("network"),
                )
            )
        records.sort(key=lambda record: record.created)
        return records

    def create_wallet(
        self,
        *,
        label: str,
        derivation_path: str = DEFAULT_DERIVATION_PATH,
        passphrase: str = "",
        network: Optional[str] = None,
    ) -> WalletRecord:
        mnemonic = self._generate_mnemonic()
        return self._store_wallet(
            label=label,
            mnemonic=mnemonic,
            derivation_path=derivation_path,
            passphrase=passphrase,
            network=network,
        )

    def import_wallet(
        self,
        *,
        label: str,
        mnemonic: str,
        derivation_path: str = DEFAULT_DERIVATION_PATH,
        passphrase: str = "",
        network: Optional[str] = None,
    ) -> WalletRecord:
        return self._store_wallet(
            label=label,
            mnemonic=mnemonic,
            derivation_path=derivation_path,
            passphrase=passphrase,
            network=network,
        )

    def export_wallet(self, *, label: str, path: Path, passphrase: str) -> Path:
        store = self._load_store()
        if label not in store:
            raise KeyError(f"Unknown wallet '{label}'")
        entry = store[label]
        mnemonic_entry = keyring_backend.get_entry(KEYRING_SERVICE, label)
        if mnemonic_entry is None or not mnemonic_entry.secret:
            raise RuntimeError("Wallet mnemonic is missing from the keyring")
        payload = {
            "wallet": {k: v for k, v in entry.items() if k != "mnemonic_passphrase"},
            "mnemonic": mnemonic_entry.secret,
            "mnemonic_passphrase": entry.get("mnemonic_passphrase", ""),
        }
        encrypted = encrypt_with_passphrase(payload, passphrase)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(encrypted, indent=2), encoding="utf-8")
        log_event("wallet.export", label=label, path=str(path))
        return path

    def import_backup(self, *, path: Path, passphrase: str) -> WalletRecord:
        payload = json.loads(path.read_text(encoding="utf-8"))
        decoded = decrypt_with_passphrase(payload, passphrase)
        label = str(decoded["wallet"]["label"])
        mnemonic = str(decoded["mnemonic"])
        return self._store_wallet(
            label=label,
            mnemonic=mnemonic,
            derivation_path=str(decoded["wallet"].get("derivation_path", DEFAULT_DERIVATION_PATH)),
            passphrase=str(decoded.get("mnemonic_passphrase", "")),
            network=decoded["wallet"].get("network"),
        )

    def _load_account(self, label: str) -> Account:
        store = self._load_store()
        if label not in store:
            raise KeyError(f"Unknown wallet '{label}'")
        entry = store[label]
        mnemonic_entry = keyring_backend.get_entry(KEYRING_SERVICE, label)
        if mnemonic_entry is None or not mnemonic_entry.secret:
            raise RuntimeError("Wallet mnemonic is missing from the keyring")
        return self._derive_account(
            mnemonic_entry.secret,
            derivation_path=str(entry.get("derivation_path", DEFAULT_DERIVATION_PATH)),
            passphrase=str(entry.get("mnemonic_passphrase", "")),
        )

    def sign_message(self, *, label: str, message: str) -> str:
        account = self._load_account(label)
        signed = account.sign_message(encode_defunct(text=message))
        log_event("wallet.sign", label=label)
        return signed.signature.hex()

    def _get_web3(self) -> Optional[Web3]:
        if self._web3 is None:
            if self._rpc_url:
                self._web3 = Web3(Web3.HTTPProvider(self._rpc_url, request_kwargs={"timeout": 10}))
            else:
                try:
                    provider = EthereumTesterProvider()  # type: ignore[call-arg]
                except ModuleNotFoundError:
                    self._web3 = None
                else:
                    self._web3 = Web3(provider)
        return self._web3

    def balance(self, *, label: str) -> Dict[str, object]:
        account = self._load_account(label)
        client = self._get_web3()
        if client is None:
            log_event("wallet.balance", label=label, balance="0", note="eth-tester unavailable")
            return {"address": account.address, "balance_wei": 0, "balance_eth": 0, "nonce": 0}
        balance_wei = client.eth.get_balance(account.address)
        nonce = client.eth.get_transaction_count(account.address)
        log_event("wallet.balance", label=label, balance=str(balance_wei))
        return {
            "address": account.address,
            "balance_wei": balance_wei,
            "balance_eth": Web3.from_wei(balance_wei, "ether"),
            "nonce": nonce,
        }

    def rotate_labels(self, *, labels: Iterable[str]) -> int:
        store = self._load_store()
        updated = 0
        for label in labels:
            if label not in store:
                continue
            mnemonic = self._generate_mnemonic()
            derivation = str(store[label].get("derivation_path", DEFAULT_DERIVATION_PATH))
            passphrase = str(store[label].get("mnemonic_passphrase", ""))
            self._store_wallet(
                label=label,
                mnemonic=mnemonic,
                derivation_path=derivation,
                passphrase=passphrase,
                network=store[label].get("network"),
            )
            updated += 1
        log_event("wallet.rotate", count=updated, labels=list(labels))
        return updated


__all__ = ["WalletManager", "WalletRecord", "DEFAULT_DERIVATION_PATH"]

