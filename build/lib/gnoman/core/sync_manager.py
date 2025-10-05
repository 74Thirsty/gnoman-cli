"""Keyring ↔ environment synchronisation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from ..utils import keyring_backend
from ..utils.env_tools import env_file_paths
from .log_manager import log_event


@dataclass
class SyncReport:
    """Detailed reconciliation results."""

    env_only: Dict[str, str]
    secure_only: Dict[str, str]
    keyring_only: Dict[str, str]
    mismatched: Dict[str, Dict[str, str]]


class SyncManager:
    """Compare `.env`, `.env.secure`, and keyring entries."""

    SERVICE = "gnoman.env"

    def __init__(self, *, root: Optional[Path] = None) -> None:
        self._paths = env_file_paths(root)

    @staticmethod
    def _load_env(path: Path) -> Dict[str, str]:
        if not path.exists():
            return {}
        entries: Dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line or line.strip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            entries[key.strip()] = value.strip()
        return entries

    def _keyring_entries(self) -> Dict[str, str]:
        result: Dict[str, str] = {}
        for entry in keyring_backend.list_all_entries():
            if entry.service != self.SERVICE:
                continue
            if not entry.username:
                continue
            secret_entry = keyring_backend.get_entry(entry.service, entry.username)
            if secret_entry and secret_entry.secret is not None:
                result[entry.username] = secret_entry.secret
        return result

    def analyse(self) -> SyncReport:
        env_values = self._load_env(self._paths["env"])
        secure_values = self._load_env(self._paths["env_secure"])
        keyring_values = self._keyring_entries()

        env_only = {k: v for k, v in env_values.items() if k not in secure_values}
        secure_only = {k: v for k, v in secure_values.items() if k not in keyring_values}
        keyring_only = {k: v for k, v in keyring_values.items() if k not in secure_values}
        mismatched: Dict[str, Dict[str, str]] = {}
        for key in secure_values:
            secure_val = secure_values[key]
            kr_val = keyring_values.get(key)
            if kr_val is not None and kr_val != secure_val:
                mismatched[key] = {"keyring": kr_val, "secure": secure_val}
        return SyncReport(env_only=env_only, secure_only=secure_only, keyring_only=keyring_only, mismatched=mismatched)

    def reconcile(self, *, update_env: bool = True, update_keyring: bool = True) -> SyncReport:
        report = self.analyse()
        env_path = self._paths["env_secure"]
        if update_env and report.keyring_only:
            current = self._load_env(env_path)
            current.update(report.keyring_only)
            env_path.write_text(
                "\n".join(f"{key}={value}" for key, value in sorted(current.items())),
                encoding="utf-8",
            )
        if update_keyring and report.secure_only:
            for key, value in report.secure_only.items():
                keyring_backend.set_entry(self.SERVICE, key, value)
        log_event(
            "sync.run",
            env_only=len(report.env_only),
            secure_only=len(report.secure_only),
            keyring_only=len(report.keyring_only),
            mismatched=len(report.mismatched),
        )
        return report


__all__ = ["SyncManager", "SyncReport"]

