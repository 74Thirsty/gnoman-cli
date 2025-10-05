from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import keyring
import keyring.backend
import pytest

from gnoman.core.secrets_manager import SecretsManager
from gnoman.utils import keyring_backend


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
    keyring.set_keyring(MemoryKeyring())
    return tmp_path


def test_secret_roundtrip_and_rotation(isolated_home: Path) -> None:
    manager = SecretsManager()
    adapter = keyring_backend.KeyringLibraryAdapter(base_path=isolated_home)
    with keyring_backend.use_adapter(adapter):
        manager.add(service="service", username="user", secret="value")
        records = manager.list(include_values=True)
        assert len(records) == 1
        assert records[0].secret == "value"

        rotated = manager.rotate(length=16)
        assert rotated == 1
        refreshed = manager.list(include_values=True)
        assert refreshed[0].secret is not None
        assert refreshed[0].secret != "value"

        manager.delete(service="service", username="user")
        assert manager.list() == []


def test_audit_reports_stale(isolated_home: Path) -> None:
    manager = SecretsManager()
    adapter = keyring_backend.KeyringLibraryAdapter(base_path=isolated_home)
    with keyring_backend.use_adapter(adapter):
        manager.add(service="service", username="user", secret="value")
        index_path = isolated_home / "secrets_index.json"
        data = json.loads(index_path.read_text(encoding="utf-8"))
        aged = datetime.now(timezone.utc) - timedelta(days=200)
        data[0]["metadata"]["modified"] = aged.isoformat()
        index_path.write_text(json.dumps(data), encoding="utf-8")

        report = keyring_backend.audit_entries(stale_days=90)
        assert report["total"] == 1
        assert report["stale"] == ["service/user"]
