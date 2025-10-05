from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from gnoman.utils import keyring_backend


@pytest.fixture()
def adapter() -> keyring_backend.InMemoryAdapter:
    return keyring_backend.InMemoryAdapter()


def test_roundtrip_and_rotation(tmp_path: Path, adapter: keyring_backend.InMemoryAdapter) -> None:
    backup = tmp_path / "backup.gnoman"
    with keyring_backend.use_adapter(adapter):
        keyring_backend.set_entry("service", "user", "secret")
        entries = keyring_backend.list_all_entries()
        assert len(entries) == 1
        assert entries[0].service == "service"
        item = keyring_backend.get_entry("service", "user")
        assert item is not None
        assert item.secret == "secret"

        exported = keyring_backend.export_all(backup, "passphrase")
        assert exported == 1

        keyring_backend.rotate_entries(services=["service"], length=24)
        rotated = keyring_backend.get_entry("service", "user")
        assert rotated is not None
        assert rotated.secret != "secret"

        keyring_backend.delete_entry("service", "user")
        assert keyring_backend.get_entry("service", "user") is None

        imported = keyring_backend.import_entries(backup, "passphrase")
        assert imported == 1
        restored = keyring_backend.get_entry("service", "user")
        assert restored is not None


def test_audit_detects_stale_entries(adapter: keyring_backend.InMemoryAdapter) -> None:
    with keyring_backend.use_adapter(adapter):
        keyring_backend.set_entry("github", "token", "value")
        # Manually age the entry inside the adapter
        entry = adapter._data[("github", "token")]
        entry["modified"] = datetime.now(timezone.utc) - timedelta(days=200)

        report = keyring_backend.audit_entries(stale_days=90)
        assert report["total"] == 1
        assert "github/token" in report["stale"]
