"""Utility helpers for GNOMAN's forensic logging system.

The real Safe/wallet integrations will fill in the actual payloads later.
For now this module just gives us a structured JSON logger that writes to
``~/.gnoman/gnoman.log`` using a rotating file handler.
"""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime, timezone

__all__ = ["ForensicLogger", "get_logger"]

_DEFAULT_LOG_PATH = Path.home() / ".gnoman" / "gnoman.log"


class ForensicLogger:
    """Emit tamper-evident style log lines suitable for forensics.

    The goal is to make every user action leave a structured trail. Actual
    signature aggregation, Safe execution, or monitoring code can call
    :meth:`log` with whatever metadata they produce.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or _DEFAULT_LOG_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._logger = logging.getLogger("gnoman.forensics")
        if not self._logger.handlers:
            self._logger.setLevel(logging.INFO)
            formatter = logging.Formatter("%(message)s")

            file_handler = RotatingFileHandler(
                self.path,
                maxBytes=2_000_000,
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)

            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)

            self._logger.addHandler(file_handler)
            self._logger.addHandler(console_handler)

    def log(self, category: str, action: str, status: str = "success", **fields: Any) -> None:
        """Record a forensic event.

        Parameters
        ----------
        category:
            Logical subsystem (e.g. ``"SAFE"`` or ``"SECRETS"``).
        action:
            Short verb describing what happened.
        status:
            ``"success"``, ``"failure"``, ``"pending"`` etc.
        **fields:
            Additional context – proposal ids, addresses, counts, etc.
        """

        timestamp = datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()
        payload: Dict[str, Any] = {"action": action, "status": status, **fields}
        serialized = json.dumps(payload, sort_keys=True)
        line = f"{timestamp} | [{category.upper()}] {serialized}"
        self._logger.info(line)


# Small convenience wrapper so other modules can just grab a shared logger.
_shared_logger: Optional[ForensicLogger] = None


def get_logger() -> ForensicLogger:
    global _shared_logger
    if _shared_logger is None:
        _shared_logger = ForensicLogger()
    return _shared_logger
