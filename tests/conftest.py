from __future__ import annotations

import base64
import secrets
import sys
from pathlib import Path

import keyring
import keyring.backend
import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class MemoryKeyring(keyring.backend.KeyringBackend):
    priority = 1

    def __init__(self) -> None:
        self._data: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self._data.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self._data[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self._data.pop((service, username), None)


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("GNOMAN_HOME", str(tmp_path))
    monkeypatch.setenv("GNOMAN_FORCE_ADAPTER", "library")
    keyring.set_keyring(MemoryKeyring())
    return tmp_path


@pytest.fixture()
def audit_key_env(monkeypatch: pytest.MonkeyPatch) -> str:
    raw = secrets.token_bytes(32)
    encoded = base64.b64encode(raw).decode("ascii")
    monkeypatch.setenv("GNOMAN-AUDIT-KEY", encoded)
    return encoded
