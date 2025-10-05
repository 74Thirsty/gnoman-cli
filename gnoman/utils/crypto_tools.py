"""Cryptographic helpers powering GNOMAN signing."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .env_tools import get_gnoman_home


def _audit_key_path() -> Path:
    base = get_gnoman_home()
    base.mkdir(parents=True, exist_ok=True)
    return base / "gnoman_audit_key.pem"


def _load_or_create_key() -> Ed25519PrivateKey:
    path = _audit_key_path()
    if path.exists():
        data = path.read_bytes()
        return serialization.load_pem_private_key(data, password=None)
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    path.write_bytes(pem)
    os.chmod(path, 0o600)
    return key


def sign_payload(payload: Any) -> str:
    """Return a base64 encoded Ed25519 signature for *payload*."""

    if isinstance(payload, (bytes, bytearray)):
        message = bytes(payload)
    else:
        message = json.dumps(payload, sort_keys=True).encode("utf-8")
    key = _load_or_create_key()
    signature = key.sign(message)
    return base64.b64encode(signature).decode("ascii")


__all__ = ["sign_payload"]
