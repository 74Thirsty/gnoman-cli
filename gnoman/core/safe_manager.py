"""Gnosis Safe orchestration powered by safe-eth-py."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

from .log_manager import log_event


@dataclass
class SafeDeployment:
    """Result of a Safe deployment."""

    address: str
    tx_hash: str


class SafeManager:
    """Integrate the ``safe-eth-py`` library with GNOMAN."""

    def __init__(self, *, rpc_url: Optional[str] = None) -> None:
        self._rpc_url = rpc_url or os.getenv("GNOMAN_ETH_RPC")

    def _safe_modules(self):  # pragma: no cover - depends on optional dependency
        try:
            from gnosis.eth import EthereumClient
            from gnosis.safe import Safe
            from gnosis.safe.safe_creation import SafeCreator
            from gnosis.safe.safe_tx_builder import SafeTxBuilder
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "safe-eth-py is required for Safe orchestration. Install gnosis-py to continue."
            ) from exc
        return EthereumClient, Safe, SafeCreator, SafeTxBuilder

    def deploy_safe(self, *, owners: List[str], threshold: Optional[int] = None, network: str = "auto") -> SafeDeployment:
        EthereumClient, Safe, SafeCreator, _ = self._safe_modules()
        client = EthereumClient(self._rpc_url or "")
        threshold_value = threshold or max(1, len(owners))
        if len(owners) < threshold_value:
            raise ValueError("Threshold cannot exceed number of owners")
        creator = SafeCreator(client.ethereum_client)
        deployment = creator.deploy_safe(owners, threshold_value)
        receipt = client.w3.eth.wait_for_transaction_receipt(deployment.tx_hash)
        safe_address = deployment.safe_address
        log_event("safe.deploy", owners=owners, threshold=threshold_value, tx=deployment.tx_hash)
        return SafeDeployment(address=safe_address, tx_hash=deployment.tx_hash.hex() if hasattr(deployment.tx_hash, "hex") else str(deployment.tx_hash))

    def manage_owners(
        self,
        *,
        safe_address: str,
        add_owner: Optional[str] = None,
        remove_owner: Optional[str] = None,
        threshold: Optional[int] = None,
    ) -> str:
        EthereumClient, Safe, _, SafeTxBuilder = self._safe_modules()
        client = EthereumClient(self._rpc_url or "")
        safe = Safe(safe_address, client.w3)
        builder = SafeTxBuilder.from_safe(safe)
        if add_owner:
            builder.add_owner_with_threshold(add_owner, threshold or safe.retrieve_threshold())
        if remove_owner:
            builder.remove_owner(remove_owner, threshold or safe.retrieve_threshold())
        tx = builder.build()
        tx_hash = client.w3.eth.send_transaction(tx.raw_transaction)
        log_event(
            "safe.manage_owners",
            safe=safe_address,
            add=add_owner,
            remove=remove_owner,
            threshold=threshold,
            tx_hash=tx_hash.hex() if hasattr(tx_hash, "hex") else str(tx_hash),
        )
        return tx_hash.hex() if hasattr(tx_hash, "hex") else str(tx_hash)

    def handle_transaction(
        self,
        *,
        safe_address: str,
        to: str,
        value: int,
        data: bytes = b"",
        operation: int = 0,
    ) -> str:
        EthereumClient, Safe, _, SafeTxBuilder = self._safe_modules()
        client = EthereumClient(self._rpc_url or "")
        safe = Safe(safe_address, client.w3)
        builder = SafeTxBuilder.from_safe(safe)
        builder.add_transaction(to, value, data, operation)
        tx = builder.build()
        tx_hash = client.w3.eth.send_transaction(tx.raw_transaction)
        log_event(
            "safe.tx",
            safe=safe_address,
            to=to,
            value=value,
            operation=operation,
            tx_hash=tx_hash.hex() if hasattr(tx_hash, "hex") else str(tx_hash),
        )
        return tx_hash.hex() if hasattr(tx_hash, "hex") else str(tx_hash)


__all__ = ["SafeManager", "SafeDeployment"]

