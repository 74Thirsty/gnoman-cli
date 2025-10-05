"""Cryptographic helpers powering GNOMAN signing."""

from __future__ import annotations

import base64
import json
import os
import secrets
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

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


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=32, n=2 ** 14, r=8, p=1)
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt_with_passphrase(payload: Any, passphrase: str) -> dict[str, str]:
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    key = _derive_key(passphrase, salt)
    cipher = ChaCha20Poly1305(key)
    plaintext = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ciphertext = cipher.encrypt(nonce, plaintext, None)
    return {
        "version": "1",
        "cipher": "chacha20poly1305",
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }


def decrypt_with_passphrase(payload: dict[str, str], passphrase: str) -> Any:
    salt = base64.b64decode(payload["salt"])
    nonce = base64.b64decode(payload["nonce"])
    ciphertext = base64.b64decode(payload["ciphertext"])
    key = _derive_key(passphrase, salt)
    cipher = ChaCha20Poly1305(key)
    plaintext = cipher.decrypt(nonce, ciphertext, None)
    return json.loads(plaintext.decode("utf-8"))


__all__ = ["decrypt_with_passphrase", "encrypt_with_passphrase", "sign_payload"]
