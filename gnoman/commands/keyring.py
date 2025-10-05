"""CLI command handlers for the keyring management surface."""

from __future__ import annotations

import getpass
import json
import sys
from pathlib import Path
from typing import Iterable, Optional

from ..utils import keyring_backend
def list_entries(namespace: Optional[str] = None, include_secrets: bool = False) -> None:
    """List every entry available in the system keyring."""

    entries = keyring_backend.list_all_entries()
    if namespace:
        entries = [entry for entry in entries if entry.service.startswith(namespace)]

    if not entries:
        print("No keyring entries found.")
        return

    width_service = max(len(entry.service) for entry in entries)
    width_user = max(len(entry.username) for entry in entries)

    header = f"{'SERVICE'.ljust(width_service)}  {'USERNAME'.ljust(width_user)}  SECRET"
    print(header)
    print("-" * len(header))
    for entry in entries:
        secret = "<hidden>"
        if include_secrets:
            secret_value = keyring_backend.get_entry(entry.service, entry.username)
            secret = secret_value.secret if secret_value and secret_value.secret is not None else "<missing>"
        print(f"{entry.service.ljust(width_service)}  {entry.username.ljust(width_user)}  {secret}")


def show_entry(service: str, username: str) -> None:
    """Display a single entry from the keyring."""

    entry = keyring_backend.get_entry(service, username)
    if entry is None:
        print(f"No entry found for service '{service}' and username '{username}'.")
        sys.exit(1)

    payload = {
        "service": entry.service,
        "username": entry.username,
        "secret": entry.secret,
        "metadata": entry.metadata,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def set_entry(service: str, username: str, secret: Optional[str] = None) -> None:
    """Create or update a keyring entry."""

    if secret is None:
        secret = getpass.getpass(prompt="Secret value: ")
    keyring_backend.set_entry(service, username, secret)
    print(f"Stored secret for {service}/{username}.")


def delete_entry(service: str, username: str, force: bool = False) -> None:
    """Remove a keyring entry, prompting for confirmation when necessary."""

    if not force:
        confirm = input(f"Delete secret for {service}/{username}? [y/N]: ")
        if confirm.strip().lower() not in {"y", "yes"}:
            print("Aborted.")
            return
    keyring_backend.delete_entry(service, username)
    print(f"Removed secret for {service}/{username}.")


def export_entries(path: str, passphrase: Optional[str] = None) -> None:
    """Export every keyring entry to *path* encrypted with *passphrase*."""

    if passphrase is None:
        passphrase = getpass.getpass(prompt="Export passphrase: ")
    exported = keyring_backend.export_all(Path(path), passphrase)
    print(f"Exported {exported} entries to {path}.")


def import_entries(path: str, passphrase: Optional[str] = None, replace_existing: bool = False) -> None:
    """Import entries from an encrypted backup file."""

    if passphrase is None:
        passphrase = getpass.getpass(prompt="Import passphrase: ")
    imported = keyring_backend.import_entries(Path(path), passphrase, replace_existing=replace_existing)
    print(f"Imported {imported} entries from {path}.")


def rotate_entries(services: Optional[Iterable[str]] = None, length: int = 32) -> None:
    """Rotate credentials for the provided services (or every service when ``None``)."""

    rotated = keyring_backend.rotate_entries(services=services, length=length)
    if not rotated:
        print("No entries were rotated.")
        return
    print(f"Rotated {rotated} keyring entries.")


def audit(stale_days: int = 180) -> None:
    """Print a summary of potential problems with the stored credentials."""

    report = keyring_backend.audit_entries(stale_days=stale_days)
    print(json.dumps(report, indent=2, ensure_ascii=False))
