"""Rotating forensic logger emitting JSON lines."""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict

LOG_ROOT = Path.home() / ".gnoman"
LOG_DIR = LOG_ROOT / "logs"
LOG_FILE = LOG_DIR / "gnoman.log"


def _get_logger() -> logging.Logger:
    logger = logging.getLogger("gnoman")
    if logger.handlers:
        return logger

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=5)
    formatter = logging.Formatter("%(message)s")

    logger.setLevel(logging.INFO)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def info(record: Dict[str, object]) -> None:
    """Write a forensic JSON record to the rotating log."""

    logger = _get_logger()
    logger.info(json.dumps(record))
