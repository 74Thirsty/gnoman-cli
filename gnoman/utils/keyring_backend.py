"""Platform aware keyring enumeration helpers."""

from __future__ import annotations

import base64
import json
import os
import secrets
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Protocol, Sequence, Tuple

import keyring
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


class KeyringAdapter(Protocol):
    """Protocol implemented by platform specific adapters."""

    def list_entries(self) -> List["KeyringEntry"]:
        ...

    def get_secret(self, service: str, username: str) -> Optional[str]:
        ...

    def set_secret(self, service: str, username: str, secret: str) -> None:
        ...

    def delete_secret(self, service: str, username: str) -> None:
        ...


@dataclass(order=True)
class KeyringEntry:
    """Represents a single keyring item."""

    service: str
    username: str
    secret: Optional[str] = None
    metadata: Dict[str, object] = field(default_factory=dict)


class SecretStorageAdapter:
    """Adapter using the SecretService D-Bus API on Linux."""

    def __init__(self) -> None:
        try:
            import secretstorage  # type: ignore
        except Exception as exc:  # pragma: no cover - import only fails on systems without dbus
            raise RuntimeError("secretstorage is required to enumerate the system keyring") from exc
        self._secretstorage = secretstorage

    def _collection(self):
        bus = self._secretstorage.dbus_init()
        collection = self._secretstorage.collection.get_default_collection(bus)
        if collection.is_locked():  # pragma: no cover - depends on host configuration
            collection.unlock()
        return collection

    def _iter_items(self):
        collection = self._collection()
        for item in collection.get_all_items():  # pragma: no cover - requires real keyring
            yield item

    def list_entries(self) -> List[KeyringEntry]:  # pragma: no cover - requires real keyring
        entries: List[KeyringEntry] = []
        for item in self._iter_items():
            attrs = item.get_attributes()
            service = attrs.get("service") or item.get_label() or ""
            username = attrs.get("username") or attrs.get("user") or ""
            metadata = {
                "created": item.get_created(),
                "modified": item.get_modified(),
                **{k: v for k, v in attrs.items() if k not in {"service", "username", "user"}},
            }
            entries.append(KeyringEntry(service=service, username=username, metadata=metadata))
        entries.sort()
        return entries

    def _find_item(self, service: str, username: str):  # pragma: no cover - requires real keyring
        for item in self._iter_items():
            attrs = item.get_attributes()
            service_attr = attrs.get("service") or item.get_label() or ""
            username_attr = attrs.get("username") or attrs.get("user") or ""
            if service_attr == service and username_attr == username:
                return item
        return None

    def get_secret(self, service: str, username: str) -> Optional[str]:  # pragma: no cover - requires real keyring
        item = self._find_item(service, username)
        if item is None:
            return None
        return item.get_secret().decode("utf-8")

    def set_secret(self, service: str, username: str, secret: str) -> None:
        keyring.set_password(service, username, secret)

    def delete_secret(self, service: str, username: str) -> None:
        try:
            keyring.delete_password(service, username)
        except keyring.errors.PasswordDeleteError:  # pragma: no cover - depends on host state
            pass


class WindowsCredentialAdapter:
    """Adapter built on top of the Windows Credential Manager APIs."""

    def __init__(self) -> None:
        try:
            import win32cred  # type: ignore
        except Exception as exc:  # pragma: no cover - import fails off Windows
            raise RuntimeError("pywin32 is required to access the Windows credential store") from exc
        self._win32cred = win32cred

    def list_entries(self) -> List[KeyringEntry]:  # pragma: no cover - requires Windows
        creds = self._win32cred.CredEnumerate(None, 0)
        entries: List[KeyringEntry] = []
        for cred in creds:
            service = cred.get("TargetName", "")
            username = cred.get("UserName", "")
            metadata = {
                "type": cred.get("Type"),
                "last_written": cred.get("LastWritten"),
            }
            entries.append(KeyringEntry(service=service, username=username, metadata=metadata))
        entries.sort()
        return entries

    def get_secret(self, service: str, username: str) -> Optional[str]:  # pragma: no cover - requires Windows
        try:
            cred = self._win32cred.CredRead(service, self._win32cred.CRED_TYPE_GENERIC, 0)
        except self._win32cred.error:
            return None
        if cred.get("UserName") != username:
            return None
        blob: bytes = cred.get("CredentialBlob", b"")
        return blob.decode("utf-16le")

    def set_secret(self, service: str, username: str, secret: str) -> None:  # pragma: no cover - requires Windows
        credential = {
            "Type": self._win32cred.CRED_TYPE_GENERIC,
            "TargetName": service,
            "UserName": username,
            "CredentialBlob": secret.encode("utf-16le"),
            "Persist": self._win32cred.CRED_PERSIST_LOCAL_MACHINE,
        }
        self._win32cred.CredWrite(credential, 0)

    def delete_secret(self, service: str, username: str) -> None:  # pragma: no cover - requires Windows
        try:
            self._win32cred.CredDelete(service, self._win32cred.CRED_TYPE_GENERIC, 0)
        except self._win32cred.error:
            pass


class MacOSKeychainAdapter:
    """Adapter wrapping the ``security`` command line tool on macOS."""

    def list_entries(self) -> List[KeyringEntry]:  # pragma: no cover - requires macOS
        import subprocess

        result = subprocess.run(
            ["security", "dump-keychain", "-d"],
            capture_output=True,
            check=False,
            text=True,
        )
        entries: List[KeyringEntry] = []
        service = ""
        account = ""
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith('"svce"'):
                parts = stripped.split('"')
                if len(parts) >= 4:
                    service = parts[3]
            elif stripped.startswith('"acct"'):
                parts = stripped.split('"')
                if len(parts) >= 4:
                    account = parts[3]
            elif stripped.startswith("0x") and service:
                entries.append(KeyringEntry(service=service, username=account))
                service = ""
                account = ""
        entries.sort()
        return entries

    def get_secret(self, service: str, username: str) -> Optional[str]:  # pragma: no cover - requires macOS
        import subprocess

        result = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", username, "-w"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    def set_secret(self, service: str, username: str, secret: str) -> None:  # pragma: no cover - requires macOS
        keyring.set_password(service, username, secret)

    def delete_secret(self, service: str, username: str) -> None:  # pragma: no cover - requires macOS
        try:
            keyring.delete_password(service, username)
        except keyring.errors.PasswordDeleteError:
            pass


class InMemoryAdapter:
    """Testing adapter that keeps everything in process memory."""

    def __init__(self) -> None:
        self._data: Dict[Tuple[str, str], Dict[str, object]] = {}

    def list_entries(self) -> List[KeyringEntry]:
        entries: List[KeyringEntry] = []
        for (svc, user), meta in self._data.items():
            metadata = dict(meta)
            metadata.pop("secret", None)
            entries.append(KeyringEntry(service=svc, username=user, metadata=metadata))
        entries.sort()
        return entries

    def get_secret(self, service: str, username: str) -> Optional[str]:
        record = self._data.get((service, username))
        if not record:
            return None
        return record.get("secret")  # type: ignore[return-value]

    def set_secret(self, service: str, username: str, secret: str) -> None:
        now = datetime.now(timezone.utc)
        meta = self._data.setdefault((service, username), {"created": now})
        meta["secret"] = secret
        meta["modified"] = now

    def delete_secret(self, service: str, username: str) -> None:
        self._data.pop((service, username), None)


_adapter_override: Optional[KeyringAdapter] = None


@contextmanager
def use_adapter(adapter: KeyringAdapter) -> Iterator[None]:
    """Context manager forcing *adapter* to be used."""

    global _adapter_override
    previous = _adapter_override
    _adapter_override = adapter
    try:
        yield
    finally:
        _adapter_override = previous


def _detect_adapter() -> KeyringAdapter:
    if _adapter_override is not None:
        return _adapter_override
    if sys.platform.startswith("linux"):
        return SecretStorageAdapter()
    if sys.platform == "darwin":
        return MacOSKeychainAdapter()
    if os.name == "nt":
        return WindowsCredentialAdapter()
    return InMemoryAdapter()


def list_all_entries() -> List[KeyringEntry]:
    """Return every entry from the active keyring backend."""

    adapter = _detect_adapter()
    return adapter.list_entries()


def get_entry(service: str, username: str) -> Optional[KeyringEntry]:
    """Retrieve a single keyring entry including the secret."""

    adapter = _detect_adapter()
    secret = adapter.get_secret(service, username)
    if secret is None:
        return None
    metadata = {}
    for entry in adapter.list_entries():
        if entry.service == service and entry.username == username:
            metadata = entry.metadata
            break
    return KeyringEntry(service=service, username=username, secret=secret, metadata=metadata)


def set_entry(service: str, username: str, secret: str) -> None:
    """Create or update an entry in the keyring."""

    adapter = _detect_adapter()
    adapter.set_secret(service, username, secret)


def delete_entry(service: str, username: str) -> None:
    """Delete an entry from the keyring."""

    adapter = _detect_adapter()
    adapter.delete_secret(service, username)


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=32, n=2 ** 14, r=8, p=1)
    return kdf.derive(passphrase.encode("utf-8"))


def _serialise_metadata(metadata: Dict[str, object]) -> Dict[str, object]:
    serialised: Dict[str, object] = {}
    for key, value in metadata.items():
        if isinstance(value, datetime):
            serialised[key] = value.isoformat()
        else:
            serialised[key] = value
    return serialised


def _encrypt_entries(entries: Sequence[KeyringEntry], passphrase: str) -> Dict[str, str]:
    salt = secrets.token_bytes(16)
    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(12)
    payload = [
        {
            "service": entry.service,
            "username": entry.username,
            "secret": entry.secret,
            "metadata": _serialise_metadata(entry.metadata),
        }
        for entry in entries
    ]
    plaintext = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return {
        "version": "1",
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }


def export_all(path: Path, passphrase: str) -> int:
    """Export every keyring entry to *path* using a passphrase protected container."""

    adapter = _detect_adapter()
    entries = []
    for entry in adapter.list_entries():
        secret = adapter.get_secret(entry.service, entry.username)
        if secret is None:
            continue
        entries.append(
            KeyringEntry(
                service=entry.service,
                username=entry.username,
                secret=secret,
                metadata=entry.metadata,
            )
        )
    container = _encrypt_entries(entries, passphrase)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(container, indent=2), encoding="utf-8")
    return len(entries)


def _decrypt_entries(payload: Dict[str, str], passphrase: str) -> List[KeyringEntry]:
    salt = base64.b64decode(payload["salt"])
    nonce = base64.b64decode(payload["nonce"])
    ciphertext = base64.b64decode(payload["ciphertext"])
    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    decoded = json.loads(plaintext.decode("utf-8"))
    result = []
    for entry in decoded:
        serialised_metadata = entry.get("metadata", {})
        normalised_metadata: Dict[str, object] = {}
        if isinstance(serialised_metadata, dict):
            for key, value in serialised_metadata.items():
                key_str = str(key)
                if isinstance(value, str):
                    try:
                        normalised_metadata[key_str] = datetime.fromisoformat(value)
                        continue
                    except ValueError:
                        pass
                normalised_metadata[key_str] = value
        result.append(
            KeyringEntry(
                service=str(entry["service"]),
                username=str(entry["username"]),
                secret=str(entry["secret"]),
                metadata=normalised_metadata,
            )
        )
    return result


def import_entries(path: Path, passphrase: str, *, replace_existing: bool = False) -> int:
    """Import keyring entries from *path* that was produced by :func:`export_all`."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = _decrypt_entries(payload, passphrase)
    adapter = _detect_adapter()
    imported = 0
    for entry in entries:
        if not replace_existing:
            current = adapter.get_secret(entry.service, entry.username)
            if current is not None:
                continue
        adapter.set_secret(entry.service, entry.username, entry.secret or "")
        imported += 1
    return imported


def rotate_entries(*, services: Optional[Iterable[str]] = None, length: int = 32) -> int:
    """Rotate credentials by generating fresh high entropy values."""

    adapter = _detect_adapter()
    whitelist = set(services) if services else None
    rotated = 0
    for entry in adapter.list_entries():
        if whitelist and entry.service not in whitelist:
            continue
        secret = secrets.token_urlsafe(length)
        adapter.set_secret(entry.service, entry.username, secret)
        rotated += 1
    return rotated


def audit_entries(*, stale_days: int = 180) -> Dict[str, object]:
    """Generate a high level report about the current keyring contents."""

    adapter = _detect_adapter()
    entries = adapter.list_entries()
    total = len(entries)
    duplicates: Dict[Tuple[str, str], int] = {}
    missing_usernames = []
    stale: List[Tuple[str, str]] = []
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=stale_days)

    for entry in entries:
        key = (entry.service, entry.username)
        duplicates[key] = duplicates.get(key, 0) + 1
        if not entry.username:
            missing_usernames.append(entry.service)
        modified = entry.metadata.get("modified") if isinstance(entry.metadata, dict) else None
        if isinstance(modified, datetime) and modified.tzinfo is None:
            modified = modified.replace(tzinfo=timezone.utc)
        if isinstance(modified, datetime) and modified < threshold:
            stale.append(key)

    duplicate_list = [f"{service}/{username}" for (service, username), count in duplicates.items() if count > 1]
    stale_list = [f"{service}/{username}" for service, username in stale]

    return {
        "total": total,
        "duplicates": sorted(duplicate_list),
        "missing_usernames": sorted(set(missing_usernames)),
        "stale": sorted(set(stale_list)),
    }


__all__ = [
    "KeyringEntry",
    "InMemoryAdapter",
    "audit_entries",
    "delete_entry",
    "export_all",
    "get_entry",
    "import_entries",
    "list_all_entries",
    "rotate_entries",
    "set_entry",
    "use_adapter",
]
