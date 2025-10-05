"""Unit tests for the wallet subsystem."""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Dict, Optional, Tuple

from gnoman.utils import keyring_index
from gnoman.security import EncryptedJSONStore
from gnoman.wallet import (
    DerivationResolver,
    HDWalletTree,
    VanityGenerator,
    WalletManager,
    WalletManagerError,
    WalletSeedManager,
)

MNEMONIC = "test test test test test test test test test test test junk"


class InMemoryKeyring:
    def __init__(self) -> None:
        self._store: Dict[Tuple[str, str], str] = {}

    def get_password(self, service: str, key: str) -> Optional[str]:
        return self._store.get((service, key))

    def set_password(self, service: str, key: str, value: str) -> None:
        self._store[(service, key)] = value

    def delete_password(self, service: str, key: str) -> None:
        self._store.pop((service, key), None)


class WalletTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="gnoman-wallet-test-"))
        self.config_path = self.temp_dir / "derivations.json"
        self.config_path.write_text(
            json.dumps(
                {
                    "default": "m/44'/60'/0'/0/{index}",
                    "trading": "m/44'/60'/0'/1/{index}",
                    "vanity": "m/44'/60'/1337'/{index}",
                }
            ),
            encoding="utf-8",
        )
        self.keyring = InMemoryKeyring()
        self.seed_manager = WalletSeedManager(service_name="test", backend=self.keyring)
        self.seed_manager.store_mnemonic(MNEMONIC)
        self.seed_manager.store_passphrase("unit-test-passphrase")
        self.resolver = DerivationResolver(config_path=self.config_path)
        self.state_path = self.temp_dir / "wallet_state.enc"
        self.store = EncryptedJSONStore(
            path=self.state_path, passphrase_resolver=lambda: "unit-test-passphrase"
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_hd_tree_reproducible_derivation(self) -> None:
        tree = HDWalletTree(self.seed_manager, self.resolver)
        addr_a, acct_a, path_a = tree.get_address(0, path_override="default")
        addr_b, acct_b, path_b = tree.get_address(0, path_override="default")
        self.assertEqual(addr_a, addr_b)
        self.assertEqual(acct_a.address, acct_b.address)
        self.assertEqual(path_a, path_b)

    def test_custom_path_resolution(self) -> None:
        path = self.resolver.resolve("trading", 7)
        self.assertEqual(path, "m/44'/60'/0'/1/7")
        explicit = self.resolver.resolve("m/44'/60'/0'/9/{index}", 3)
        self.assertEqual(explicit, "m/44'/60'/0'/9/3")

    def test_vanity_generator_logs_on_success(self) -> None:
        tree = HDWalletTree(self.seed_manager, self.resolver)
        generator = VanityGenerator(tree, "vanity", log_every=1)
        with self.assertLogs("gnoman.wallet", level=logging.INFO) as captured:
            result = generator.find_match(prefix="0x", max_attempts=5)
        self.assertEqual(result["index"], 0)
        self.assertTrue(any("[VanityGenerator] ✅ Found vanity" in msg for msg in captured.output))

    def test_wallet_manager_persists_vanity_metadata(self) -> None:
        manager = WalletManager(
            seed_manager=self.seed_manager,
            resolver=self.resolver,
            state_path=self.state_path,
            store=self.store,
        )
        record = manager.find_vanity(prefix="0x", max_attempts=5, log_every=1)
        metadata_key = f"wallet_vanity::{record.address}".lower()
        stored = self.seed_manager.get_metadata(metadata_key)
        self.assertIsNotNone(stored)
        payload = json.loads(stored)
        self.assertEqual(payload["index"], record.index)
        self.assertEqual(payload["path"], record.derivation_path)

    def test_create_account_raises_without_unique_label(self) -> None:
        manager = WalletManager(
            seed_manager=self.seed_manager,
            resolver=self.resolver,
            state_path=self.state_path,
            store=self.store,
        )
        manager.create_account("alpha", path="default")
        with self.assertRaises(WalletManagerError):
            manager.create_account("alpha", path="default")

    def test_seed_manager_tracks_keys_in_index(self) -> None:
        keys = keyring_index.list_keys(self.keyring, "test")
        self.assertIn(self.seed_manager.MNEMONIC_KEY, keys)
        self.seed_manager.clear_mnemonic()
        keys_after = keyring_index.list_keys(self.keyring, "test")
        self.assertNotIn(self.seed_manager.MNEMONIC_KEY, keys_after)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
