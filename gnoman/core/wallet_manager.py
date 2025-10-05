"""Wallet lifecycle management stubs."""

from __future__ import annotations

from typing import Optional

from .log_manager import log_event


class WalletManager:
    """Placeholder for HD wallet functionality."""

    def create_wallet(self, *, path: Optional[str] = None) -> None:
        log_event("wallet-create", path=path)
        raise NotImplementedError("HD wallet generation has not been implemented yet")

    def import_wallet(self, *, mnemonic: Optional[str], private_key: Optional[str]) -> None:
        log_event("wallet-import", mnemonic=bool(mnemonic), private_key=bool(private_key))
        raise NotImplementedError("Wallet import workflows are pending implementation")

    def show_wallet(self, *, address: str, network: str) -> None:
        log_event("wallet-show", address=address, network=network)
        raise NotImplementedError("Wallet inspection requires Web3 integration")


__all__ = ["WalletManager"]
