"""Contract ABI management stubs."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .log_manager import log_event


class ContractManager:
    """Placeholder for ABI lifecycle operations."""

    def load_contract(self, *, path: str, name: Optional[str]) -> None:
        log_event("contract-load", path=path, name=name)
        _ = Path(path)  # Trigger path validation for callers
        raise NotImplementedError("Contract loading is not yet implemented")


__all__ = ["ContractManager"]
