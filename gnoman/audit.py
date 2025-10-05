"""Audit logging utilities for the GNOMAN control surface."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ed25519

try:  # pragma: no cover - keyring availability depends on host
    import keyring  # type: ignore
except Exception:  # pragma: no cover - importing keyring can legitimately fail
    keyring = None  # type: ignore


AUDIT_DIRECTORY = Path.home() / ".gnoman"
AUDIT_LOG_PATH = AUDIT_DIRECTORY / "gnoman_audit.jsonl"
AUDIT_SERVICE = "gnoman-audit"
AUDIT_KEY_NAME = "GNOMAN-AUDIT-KEY"


@dataclass(slots=True)
class AuditRecord:
    """Structured representation of a single audit entry."""

    prev: str
    body: Dict[str, Any]
    hash: str
    signature: str


def _load_last_record_hash() -> str:
    if not AUDIT_LOG_PATH.exists():
        return ""
    try:
        with AUDIT_LOG_PATH.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            position = handle.tell()
            buffer = b""
            step = 2048
            while position > 0:
                position = max(0, position - step)
                handle.seek(position)
                chunk = handle.read(step)
                buffer = chunk + buffer
                if b"\n" in buffer:
                    break
            lines = buffer.splitlines()
            if not lines:
                return ""
            payload = json.loads(lines[-1].decode("utf-8"))
            return str(payload.get("hash", ""))
    except Exception:
        return ""


def _load_private_key_bytes() -> bytes:
    """Return the raw Ed25519 private key bytes from the keyring or environment."""

    candidates: List[str] = []
    if keyring is not None:
        try:
            stored = keyring.get_password(AUDIT_SERVICE, AUDIT_KEY_NAME)
        except Exception:  # pragma: no cover - backend failures depend on host
            stored = None
        if stored:
            candidates.append(stored)
    env_value = os.getenv(AUDIT_KEY_NAME)
    if env_value:
        candidates.append(env_value)
    for candidate in candidates:
        try:
            data = base64.b64decode(candidate.strip())
        except Exception as exc:
            raise ValueError("Audit key must be base64 encoded Ed25519 private key bytes") from exc
        if len(data) != 32:
            raise ValueError("GNOMAN audit key must contain exactly 32 bytes for Ed25519")
        return data
    raise NotImplementedError(
        "GNOMAN audit signing key is unavailable. Store a base64 encoded Ed25519 private key in "
        "the GNOMAN-AUDIT-KEY environment variable or the system keyring under service 'gnoman-audit'."
    )


def _build_private_key() -> ed25519.Ed25519PrivateKey:
    raw = _load_private_key_bytes()
    return ed25519.Ed25519PrivateKey.from_private_bytes(raw)


def _calculate_hash(prev_hash: str, payload: Dict[str, Any]) -> str:
    digest = hashes.Hash(hashes.SHA256())
    digest.update(json.dumps({"prev": prev_hash, **payload}, sort_keys=True).encode("utf-8"))
    return digest.finalize().hex()


def _sign_payload(private_key: ed25519.Ed25519PrivateKey, payload: Dict[str, Any]) -> str:
    message = json.dumps(payload, sort_keys=True).encode("utf-8")
    signature = private_key.sign(message)
    return base64.b64encode(signature).decode("ascii")


def append_record(action: str, params: Dict[str, Any], ok: bool, result: Dict[str, Any]) -> AuditRecord:
    """Append a new audit record and return the structured entry."""

    AUDIT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": float(time.time()),
        "action": action,
        "params": params,
        "ok": ok,
        "result": result,
    }
    previous_hash = _load_last_record_hash()
    record_hash = _calculate_hash(previous_hash, payload)
    private_key = _build_private_key()
    record_body = {"prev": previous_hash, **payload, "hash": record_hash}
    signature = _sign_payload(private_key, record_body)
    entry = {**record_body, "signature": signature}
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return AuditRecord(prev=previous_hash, body=payload, hash=record_hash, signature=signature)


def verify_tail(entries: Iterable[Dict[str, Any]]) -> bool:
    """Validate the signature of the most recent audit entries."""

    try:
        private_key = _build_private_key()
    except NotImplementedError:
        return False
    public_key = private_key.public_key()
    for entry in entries:
        payload = dict(entry)
        signature_encoded = str(payload.pop("signature", ""))
        if not signature_encoded:
            return False
        try:
            signature = base64.b64decode(signature_encoded)
        except Exception:
            return False
        message = json.dumps(payload, sort_keys=True).encode("utf-8")
        try:
            public_key.verify(signature, message)
        except InvalidSignature:
            return False
    return True


def read_tail(lines: int = 5) -> List[str]:
    """Return the newest *lines* entries from the audit log as raw JSON strings."""

    if not AUDIT_LOG_PATH.exists():
        return []
    with AUDIT_LOG_PATH.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        file_size = handle.tell()
        block_size = 2048
        data = b""
        offset = file_size
        while offset > 0 and data.count(b"\n") <= lines:
            offset = max(0, offset - block_size)
            handle.seek(offset)
            data = handle.read(file_size - offset) + data
            block_size *= 2
        decoded = data.decode("utf-8", errors="ignore").strip().splitlines()
        return decoded[-lines:]


def read_tail_records(lines: int = 5) -> List[Dict[str, Any]]:
    """Return parsed JSON objects from the newest audit log entries."""

    records: List[Dict[str, Any]] = []
    for raw in read_tail(lines):
        try:
            records.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return records


__all__ = [
    "AUDIT_DIRECTORY",
    "AUDIT_LOG_PATH",
    "AuditRecord",
    "append_record",
    "read_tail",
    "read_tail_records",
    "verify_tail",
]

