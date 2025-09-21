"""Hierarchical deterministic wallet tree management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import Web3

from .resolver import DerivationResolver
from .seed import SeedNotFoundError, WalletSeedManager

Account.enable_unaudited_hdwallet_features()


@dataclass
class HDWalletTree:
    """Hidden HD wallet tree handling keyed by the shared seed."""

    seed_manager: WalletSeedManager
    resolver: DerivationResolver

    def get_address(self, index: int, path_override: Optional[str] = None) -> Tuple[str, LocalAccount, str]:
        """Return ``(address, LocalAccount, derivation_path)`` for ``index``.

        ``path_override`` may be either a named template from the resolver
        configuration or an explicit derivation string.
        """

        identifier = path_override or "default"
        try:
            path = self.resolver.resolve(identifier, index)
            mnemonic = self.seed_manager.get_mnemonic()
            passphrase = self.seed_manager.get_passphrase()
        except SeedNotFoundError:
            raise
        account = Account.from_mnemonic(mnemonic, account_path=path, passphrase=passphrase)
        address = Web3.to_checksum_address(account.address)
        return address, account, path
