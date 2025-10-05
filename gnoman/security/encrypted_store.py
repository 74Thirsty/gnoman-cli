"""Encrypted persistence helpers backed by AES-GCM."""

from __future__ import annotations

import base64
import json
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional, TypeVar

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from ..utils.paths import state_dir

T = TypeVar("T")


class EncryptedStoreError(RuntimeError):
    """Raised when encrypted persistence fails."""


@dataclass
class EncryptedJSONStore:
    """Persist JSON serialisable payloads encrypted at rest.

    The store derives an AES-256 key from a passphrase using PBKDF2-HMAC-SHA256
    and seals payloads using AES-GCM. The encrypted artefact lives inside the
    GNOMAN state directory by default and includes metadata for replay-safe
    decryption and tamper detection.
    """

    path: Optional[Path] = None
    passphrase_resolver: Callable[[], str] = lambda: ""  # type: ignore[arg-type]
    iterations: int = 200_000
    kdf_salt_bytes: int = 16
    nonce_bytes: int = 12
    associated_data: Optional[bytes] = None
    _resolved_path: Path = field(init=False, repr=False)

    def __post_init__(self) -> None:
        base_dir = state_dir() / "secrets"
        base_dir.mkdir(parents=True, exist_ok=True)
        target = self.path or (base_dir / "wallet_accounts.enc")
        self._resolved_path = target
        self._resolved_path.parent.mkdir(parents=True, exist_ok=True)

    # -- public API -----------------------------------------------------
    def load(self, default: Optional[T] = None) -> T:
        """Decrypt and return the stored payload.

        Parameters
        ----------
        default:
            Value returned when the backing file does not exist. The object is
            returned unchanged to avoid accidental mutation.
        """

        if not self._resolved_path.exists():
            return default if default is not None else {}  # type: ignore[return-value]
        try:
            payload = json.loads(self._resolved_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:  # pragma: no cover - corrupted file
            raise EncryptedStoreError("encrypted payload is not valid JSON") from exc
        salt = _b64decode_field(payload, "salt")
        nonce = _b64decode_field(payload, "nonce")
        ciphertext = _b64decode_field(payload, "ciphertext")
        passphrase = self._get_passphrase()
        key = self._derive_key(passphrase, salt)
        aesgcm = AESGCM(key)
        try:
            plaintext = aesgcm.decrypt(nonce, ciphertext, self.associated_data)
        except InvalidTag as exc:
            raise EncryptedStoreError("decryption failed (invalid tag)") from exc
        except Exception as exc:  # pragma: no cover - unexpected backend issue
            raise EncryptedStoreError("failed to decrypt payload") from exc
        try:
            return json.loads(plaintext.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise EncryptedStoreError("decrypted payload is not valid JSON") from exc

    def save(self, payload: Dict[str, Any]) -> None:
        """Encrypt *payload* and persist it to disk."""

        encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
        passphrase = self._get_passphrase()
        salt = os.urandom(self.kdf_salt_bytes)
        nonce = secrets.token_bytes(self.nonce_bytes)
        key = self._derive_key(passphrase, salt)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, encoded, self.associated_data)
        envelope = {
            "version": 1,
            "kdf": "pbkdf2-hmac-sha256",
            "iterations": self.iterations,
            "salt": base64.b64encode(salt).decode("ascii"),
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        }
        self._resolved_path.write_text(json.dumps(envelope, indent=2), encoding="utf-8")

    def rotate_passphrase(self, new_passphrase: str) -> None:
        """Re-encrypt the payload with *new_passphrase* while preserving data."""

        if not new_passphrase:
            raise EncryptedStoreError("new passphrase must not be empty")
        data = self.load({})
        original_resolver = self.passphrase_resolver
        try:
            self.passphrase_resolver = lambda: new_passphrase
            self.save(data)
        finally:
            self.passphrase_resolver = original_resolver

    # -- helpers --------------------------------------------------------
    def _derive_key(self, passphrase: str, salt: bytes) -> bytes:
        if not passphrase:
            raise EncryptedStoreError("wallet passphrase is not configured")
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self.iterations,
        )
        return kdf.derive(passphrase.encode("utf-8"))

    def _get_passphrase(self) -> str:
        try:
            return self.passphrase_resolver()
        except EncryptedStoreError:
            raise
        except Exception as exc:  # pragma: no cover - defensive guard
            raise EncryptedStoreError("failed to resolve passphrase") from exc


def _b64decode_field(payload: Dict[str, Any], field: str) -> bytes:
    if field not in payload:
        raise EncryptedStoreError(f"missing field {field!r} in encrypted payload")
    try:
        return base64.b64decode(payload[field])
    except Exception as exc:  # pragma: no cover - invalid base64
        raise EncryptedStoreError(f"failed to decode field {field!r}") from exc
