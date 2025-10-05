"""JSON structured logging with deterministic signing."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from ..utils.crypto_tools import sign_payload
from ..utils.env_tools import get_gnoman_home


def _log_path() -> Path:
    base = get_gnoman_home()
    base.mkdir(parents=True, exist_ok=True)
    return base / "gnoman_audit.jsonl"


def log_event(action: str, **payload: Any) -> None:
    """Append a signed JSON event to the audit trail."""

    entry: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        **payload,
    }
    signature = sign_payload(entry)
    entry["signature"] = signature
    log_file = _log_path()
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True))
        handle.write(os.linesep)


__all__ = ["log_event"]
