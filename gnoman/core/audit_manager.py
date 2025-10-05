"""Forensic audit tooling stubs."""

from __future__ import annotations

from typing import Optional

from ..utils import keyring_backend
from .log_manager import log_event


class AuditManager:
    """Placeholder audit pipeline."""

    def run_audit(self, *, output: Optional[str]) -> None:
        log_event("audit-run", output=output)
        _ = keyring_backend.audit_entries()
        raise NotImplementedError("Full forensic audit reporting is not yet implemented")


__all__ = ["AuditManager"]
