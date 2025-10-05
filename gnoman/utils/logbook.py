"""Rotating forensic logger emitting tamper-evident JSON lines."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from .paths import state_dir

LOG_ROOT = state_dir()
LOG_DIR = LOG_ROOT / "logs"
LOG_FILE = LOG_DIR / "gnoman.log"
AUDIT_LOG = LOG_ROOT / "audit.jsonl"
AUDIT_KEY = LOG_ROOT / "audit_ed25519.pem"


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


def _load_or_create_key() -> ed25519.Ed25519PrivateKey:
    AUDIT_KEY.parent.mkdir(parents=True, exist_ok=True)
    if AUDIT_KEY.exists():
        data = AUDIT_KEY.read_bytes()
        return serialization.load_pem_private_key(data, password=None)
    key = ed25519.Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    AUDIT_KEY.write_bytes(pem)
    os.chmod(AUDIT_KEY, 0o600)
    return key


def _last_hash() -> Optional[str]:
    if not AUDIT_LOG.exists():
        return None
    try:
        lines = AUDIT_LOG.read_text(encoding="utf-8").strip().splitlines()
    except Exception:
        return None
    if not lines:
        return None
    try:
        payload = json.loads(lines[-1])
        return payload.get("hash")
    except Exception:
        return None


def _write_audit_record(record: Dict[str, object]) -> None:
    key = _load_or_create_key()
    prev_hash = _last_hash()
    entry = {
        "ts": time.time(),
        "prev": prev_hash,
        "record": record,
    }
    canonical = json.dumps(entry, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(canonical).digest()
    signature = key.sign(digest)
    entry["hash"] = hashlib.sha256(canonical).hexdigest()
    entry["signature"] = base64.b64encode(signature).decode("ascii")
    entry["public_key"] = base64.b64encode(
        key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).decode("ascii")
    with AUDIT_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")


def info(record: Dict[str, object]) -> None:
    """Write a forensic JSON record to the rotating log."""

    logger = _get_logger()
    logger.info(json.dumps(record))
    _write_audit_record(record)
