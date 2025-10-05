"""Gnosis Safe orchestration stubs."""

from __future__ import annotations

from typing import List, Optional

from .log_manager import log_event


class SafeManager:
    """Placeholder orchestrator for Safe-ETH integration."""

    def deploy_safe(self, *, owners: List[str], threshold: Optional[int], network: str) -> None:
        log_event("safe-deploy", owners=owners, threshold=threshold, network=network)
        raise NotImplementedError("Safe deployment requires safe-eth-py integration")

    def manage_owners(
        self,
        *,
        safe_address: str,
        add_owner: Optional[str],
        remove_owner: Optional[str],
        network: str,
    ) -> None:
        log_event(
            "safe-owners",
            safe_address=safe_address,
            add_owner=add_owner,
            remove_owner=remove_owner,
            network=network,
        )
        raise NotImplementedError("Safe owner management is not yet implemented")

    def handle_transaction(
        self,
        *,
        safe_address: str,
        action: Optional[str],
        payload: Optional[str],
        network: str,
    ) -> None:
        log_event(
            "safe-transaction",
            safe_address=safe_address,
            action=action,
            payload=payload,
            network=network,
        )
        raise NotImplementedError("Safe transaction orchestration is pending implementation")


__all__ = ["SafeManager"]
