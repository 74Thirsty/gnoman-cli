from __future__ import annotations

from pathlib import Path

from gnoman.core.wallet_manager import WalletManager
from gnoman.utils import keyring_backend


def test_wallet_create_and_sign(isolated_home: Path) -> None:
    manager = WalletManager()
    record = manager.create_wallet(label="ops")
    assert record.address.startswith("0x")

    entry = keyring_backend.get_entry("gnoman.wallet", "ops")
    assert entry is not None and entry.secret

    signature = manager.sign_message(label="ops", message="ping")
    assert signature.startswith("0x") or len(signature) in {130, 132}

    balance = manager.balance(label="ops")
    assert balance["address"] == record.address
    assert "balance_wei" in balance


def test_wallet_export_import_backup(isolated_home: Path, tmp_path: Path) -> None:
    manager = WalletManager()
    record = manager.create_wallet(label="backup", passphrase="secret")
    target = tmp_path / "wallet.enc.json"
    manager.export_wallet(label="backup", path=target, passphrase="exportpass")

    restored = manager.import_backup(path=target, passphrase="exportpass")
    assert restored.label == "backup"
    assert restored.address == record.address
