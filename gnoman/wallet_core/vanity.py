"""Vanity address generation utilities."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from .hd import HDWalletTree

logger = logging.getLogger("gnoman.wallet")


class VanitySearchError(RuntimeError):
    """Raised when vanity search encounters an error."""


@dataclass
class VanityGenerator:
    """Iteratively search for addresses matching vanity patterns."""

    tree: HDWalletTree
    path_identifier: str
    log_every: int = 5_000

    def find_match(
        self,
        *,
        prefix: Optional[str] = None,
        suffix: Optional[str] = None,
        regex: Optional[str] = None,
        max_attempts: int = 1_000_000,
    ):
        """Return the first match for the requested vanity pattern."""

        if not any([prefix, suffix, regex]):
            raise VanitySearchError("a prefix, suffix, or regex pattern is required")
        pattern = re.compile(regex, re.IGNORECASE) if regex else None
        attempts = 0
        while attempts < max_attempts:
            address, account, path = self.tree.get_address(attempts, path_override=self.path_identifier)
            candidate = address.lower()
            if self._matches(candidate, prefix, suffix, pattern):
                logger.info("[VanityGenerator] ✅ Found vanity %s at index %s", address, attempts)
                return {
                    "address": address,
                    "account": account,
                    "index": attempts,
                    "derivation_path": path,
                }
            attempts += 1
            if attempts % max(1, self.log_every) == 0:
                logger.info(
                    "[VanityGenerator] 🔍 %s attempts without match (path=%s)",
                    attempts,
                    self.path_identifier,
                )
        raise VanitySearchError("vanity search exhausted without success")

    def _matches(
        self,
        address: str,
        prefix: Optional[str],
        suffix: Optional[str],
        pattern: Optional[re.Pattern[str]],
    ) -> bool:
        prefix_l = prefix.lower() if prefix else None
        suffix_l = suffix.lower() if suffix else None
        if prefix_l and not address.startswith(prefix_l):
            return False
        if suffix_l and not address.endswith(suffix_l):
            return False
        if pattern and not pattern.search(address):
            return False
        return True
