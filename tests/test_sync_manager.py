from __future__ import annotations

from pathlib import Path

from gnoman.core.sync_manager import SyncManager
from gnoman.utils import keyring_backend


def test_sync_detects_and_reconciles(isolated_home: Path, tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_secure_path = tmp_path / ".env.secure"
    env_path.write_text("PLAIN=1\n", encoding="utf-8")
    env_secure_path.write_text("SECRET=top\n", encoding="utf-8")

    manager = SyncManager(root=tmp_path)
    report = manager.reconcile()

    assert "PLAIN" in report.env_only
    assert "SECRET" in report.secure_only

    # Keyring now contains SECRET after reconciliation
    entry = keyring_backend.get_entry("gnoman.env", "SECRET")
    assert entry is not None and entry.secret == "top"
