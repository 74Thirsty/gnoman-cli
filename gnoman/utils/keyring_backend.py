"""Platform aware keyring integration helpers."""

from __future__ import annotations

import json
import os
import secrets
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Protocol, Tuple

import keyring
from keyring.errors import PasswordDeleteError

from .env_tools import get_gnoman_home


@dataclass(order=True)
class KeyringEntry:
    """Representation of an entry stored in the keyring."""

    service: str
    username: str
    secret: Optional[str] = None
    metadata: Optional[Dict[str, object]] = None


class KeyringAdapter(Protocol):
    """Protocol implemented by every platform backend."""

    def list_entries(self) -> List[KeyringEntry]:
        ...

    def get_secret(self, service: str, username: str) -> Optional[str]:
        ...

    def set_secret(self, service: str, username: str, secret: str) -> None:
        ...

    def delete_secret(self, service: str, username: str) -> None:
        ...


class KeyringLibraryAdapter:
    """Adapter built on top of :mod:`keyring` with a deterministic index."""

    def __init__(self, base_path: Optional[Path] = None) -> None:
        self._base_path = base_path or get_gnoman_home()
        self._index_path = self._base_path / "secrets_index.json"

    def _load_index(self) -> Dict[Tuple[str, str], Dict[str, object]]:
        if not self._index_path.exists():
            return {}
        data = json.loads(self._index_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return {}
        index: Dict[Tuple[str, str], Dict[str, object]] = {}
        for entry in data:
            if not isinstance(entry, dict):
                continue
            service = str(entry.get("service", ""))
            username = str(entry.get("username", ""))
            metadata = entry.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            index[(service, username)] = dict(metadata)
        return index

    def _save_index(self, index: Dict[Tuple[str, str], Dict[str, object]]) -> None:
        payload = [
            {
                "service": service,
                "username": username,
                "metadata": metadata,
            }
            for (service, username), metadata in sorted(index.items())
        ]
        self._base_path.mkdir(parents=True, exist_ok=True)
        self._index_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @staticmethod
    def _normalise_metadata(metadata: Dict[str, object]) -> Dict[str, object]:
        normalised: Dict[str, object] = {}
        for key, value in metadata.items():
            if isinstance(value, str):
                try:
                    normalised[key] = datetime.fromisoformat(value)
                    continue
                except ValueError:
                    pass
            normalised[key] = value
        return normalised

    def list_entries(self) -> List[KeyringEntry]:
        entries: List[KeyringEntry] = []
        for (service, username), metadata in self._load_index().items():
            entries.append(
                KeyringEntry(
                    service=service,
                    username=username,
                    metadata=self._normalise_metadata(metadata),
                )
            )
        entries.sort()
        return entries

    def get_secret(self, service: str, username: str) -> Optional[str]:
        secret = keyring.get_password(service, username)
        if secret is None:
            return None
        index = self._load_index()
        metadata = index.get((service, username), {})
        metadata["last_accessed"] = datetime.now(timezone.utc).isoformat()
        index[(service, username)] = metadata
        self._save_index(index)
        return secret

    def set_secret(self, service: str, username: str, secret: str) -> None:
        keyring.set_password(service, username, secret)
        index = self._load_index()
        metadata = index.get((service, username), {})
        now = datetime.now(timezone.utc).isoformat()
        metadata.setdefault("created", now)
        metadata["modified"] = now
        index[(service, username)] = metadata
        self._save_index(index)

    def delete_secret(self, service: str, username: str) -> None:
        try:
            keyring.delete_password(service, username)
        except PasswordDeleteError:
            pass
        index = self._load_index()
        if (service, username) in index:
            del index[(service, username)]
            self._save_index(index)


class SecretStorageAdapter:
    """Adapter using the SecretService DBus API on Linux."""

    def __init__(self) -> None:
        try:
            import secretstorage  # type: ignore
        except Exception as exc:  # pragma: no cover - import specific to Linux
            raise RuntimeError("secretstorage is required for SecretService access") from exc
        self._secretstorage = secretstorage

    def _collection(self):  # pragma: no cover - requires host integration
        bus = self._secretstorage.dbus_init()
        collection = self._secretstorage.collection.get_default_collection(bus)
        if collection.is_locked():
            collection.unlock()
        return collection

    def _iter_items(self):  # pragma: no cover - requires host integration
        collection = self._collection()
        for item in collection.get_all_items():
            yield item

    def list_entries(self) -> List[KeyringEntry]:  # pragma: no cover - requires host integration
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

    def get_secret(self, service: str, username: str) -> Optional[str]:  # pragma: no cover
        for item in self._iter_items():
            attrs = item.get_attributes()
            service_attr = attrs.get("service") or item.get_label() or ""
            username_attr = attrs.get("username") or attrs.get("user") or ""
            if service_attr == service and username_attr == username:
                return item.get_secret().decode("utf-8")
        return None

    def set_secret(self, service: str, username: str, secret: str) -> None:
        keyring.set_password(service, username, secret)

    def delete_secret(self, service: str, username: str) -> None:
        try:
            keyring.delete_password(service, username)
        except PasswordDeleteError:
            pass


class WindowsCredentialAdapter:
    """Adapter built on top of the Windows Credential Manager API."""

    def __init__(self) -> None:
        try:
            import win32cred  # type: ignore
        except Exception as exc:  # pragma: no cover - import specific to Windows
            raise RuntimeError("pywin32 is required to access the credential store") from exc
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

    def get_secret(self, service: str, username: str) -> Optional[str]:  # pragma: no cover
        try:
            cred = self._win32cred.CredRead(service, self._win32cred.CRED_TYPE_GENERIC, 0)
        except self._win32cred.error:
            return None
        if cred.get("UserName") != username:
            return None
        blob: bytes = cred.get("CredentialBlob", b"")
        return blob.decode("utf-16le")

    def set_secret(self, service: str, username: str, secret: str) -> None:  # pragma: no cover
        credential = {
            "Type": self._win32cred.CRED_TYPE_GENERIC,
            "TargetName": service,
            "UserName": username,
            "CredentialBlob": secret.encode("utf-16le"),
            "Persist": self._win32cred.CRED_PERSIST_LOCAL_MACHINE,
        }
        self._win32cred.CredWrite(credential, 0)

    def delete_secret(self, service: str, username: str) -> None:  # pragma: no cover
        try:
            self._win32cred.CredDelete(service, self._win32cred.CRED_TYPE_GENERIC, 0)
        except self._win32cred.error:
            pass


class MacOSKeychainAdapter:
    """Adapter that shells out to the macOS ``security`` CLI."""

    def list_entries(self) -> List[KeyringEntry]:  # pragma: no cover - requires macOS
        import subprocess

        result = subprocess.run(
            ["security", "dump-keychain", "-d"],
            capture_output=True,
            text=True,
            check=False,
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

    def get_secret(self, service: str, username: str) -> Optional[str]:  # pragma: no cover
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

    def set_secret(self, service: str, username: str, secret: str) -> None:  # pragma: no cover
        keyring.set_password(service, username, secret)

    def delete_secret(self, service: str, username: str) -> None:  # pragma: no cover
        try:
            keyring.delete_password(service, username)
        except PasswordDeleteError:
            pass


_adapter_override: Optional[KeyringAdapter] = None


@contextmanager
def use_adapter(adapter: KeyringAdapter) -> Iterator[None]:
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
    forced = os.environ.get("GNOMAN_FORCE_ADAPTER")
    if forced == "library":
        return KeyringLibraryAdapter()
    if sys.platform.startswith("linux"):
        try:
            return SecretStorageAdapter()
        except RuntimeError:
            pass
    if sys.platform == "darwin":
        return MacOSKeychainAdapter()
    if os.name == "nt":
        try:
            return WindowsCredentialAdapter()
        except RuntimeError:
            pass
    return KeyringLibraryAdapter()


def list_all_entries() -> List[KeyringEntry]:
    adapter = _detect_adapter()
    return adapter.list_entries()


def get_entry(service: str, username: str) -> Optional[KeyringEntry]:
    adapter = _detect_adapter()
    secret = adapter.get_secret(service, username)
    if secret is None:
        return None
    for entry in adapter.list_entries():
        if entry.service == service and entry.username == username:
            return KeyringEntry(
                service=service,
                username=username,
                secret=secret,
                metadata=entry.metadata,
            )
    return KeyringEntry(service=service, username=username, secret=secret, metadata={})


def set_entry(service: str, username: str, secret: str) -> None:
    adapter = _detect_adapter()
    adapter.set_secret(service, username, secret)


def delete_entry(service: str, username: str) -> None:
    adapter = _detect_adapter()
    adapter.delete_secret(service, username)


def rotate_entries(*, services: Optional[Iterable[str]] = None, length: int = 32) -> int:
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
    adapter = _detect_adapter()
    entries = adapter.list_entries()
    total = len(entries)
    duplicates: Dict[Tuple[str, str], int] = {}
    missing_usernames = []
    stale: List[Tuple[str, str]] = []
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=stale_days) if stale_days else None

    for entry in entries:
        key = (entry.service, entry.username)
        duplicates[key] = duplicates.get(key, 0) + 1
        if not entry.username:
            missing_usernames.append(entry.service)
        metadata = entry.metadata or {}
        modified = metadata.get("modified")
        if isinstance(modified, datetime) and threshold and modified < threshold:
            stale.append(key)

    duplicate_list = [f"{service}/{username}" for (service, username), count in duplicates.items() if count > 1]
    stale_list = [f"{service}/{username}" for service, username in stale]

    return {
        "total": total,
        "duplicates": sorted(set(duplicate_list)),
        "missing_usernames": sorted(set(missing_usernames)),
        "stale": sorted(set(stale_list)),
    }


__all__ = [
    "KeyringEntry",
    "KeyringLibraryAdapter",
    "audit_entries",
    "delete_entry",
    "get_entry",
    "list_all_entries",
    "rotate_entries",
    "set_entry",
    "use_adapter",
]
